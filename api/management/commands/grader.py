# flake8: noqa: F841

import contextlib
import json
import logging as log
from math import ceil
import os
import re
import shutil
import signal
import stat
import time


from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db import (
    DatabaseError,
    OperationalError,
    transaction,
    close_old_connections,
)

from api.models import Submission, Result, Compiler
from .__utils import compress_output_lines, get_exitcode_stdout_stderr


# https://github.com/MatcomOnlineGrader/safeexec/blob/22cd436f2d384d2a933428c5f5f8240c406f08db/safeexec.c#L38C20-L38C27
LARGECONST = 4194304  # 4GiB

# `--cpu` (RLIMIT_CPU) counts only CPU the program burns, so it is the real
# limit. `--clock` is wall-clock time, which also counts time spent waiting on a
# busy host; it is only a loose backstop for programs that hang without using
# CPU. Keeping them equal made fast solutions TLE whenever the host was busy.
CLOCK_LIMIT_MULTIPLIER = 4
CLOCK_LIMIT_EXTRA_SECONDS = 5  # 1s -> 9s, 10s -> 45s

# A TLE that used less than this share of its CPU limit was most likely a
# wall-clock kill caused by host contention. Only used for logging.
SUSPICIOUS_CPU_FRACTION = 0.7


class StopRequest:
    """Turns SIGTERM (docker stop) and SIGINT (Ctrl+C) into a graceful stop:
    the grader finishes the submission it is grading, takes no new ones, and
    exits."""

    def __init__(self):
        self.requested = False
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

    def _on_signal(self, signum, frame):
        log.info(
            "Received %s; stopping after the current submission",
            signal.Signals(signum).name,
        )
        self.requested = True

    @contextlib.contextmanager
    def held(self):
        """Delay stop signals until the block ends, so it runs entirely
        before or entirely after a stop is requested."""
        stop_signals = {signal.SIGTERM, signal.SIGINT}
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, stop_signals)
        try:
            yield
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def get_clock_limit(time_limit: int) -> int:
    """Wall-clock backstop for `time_limit` seconds of CPU; see above.

    int(): per-compiler limits come from free-form JSON and may be strings.
    """
    return int(time_limit) * CLOCK_LIMIT_MULTIPLIER + CLOCK_LIMIT_EXTRA_SECONDS


def parse_uids(value):
    """Parse a SAFEEXEC_UIDS value like "10000-19999" into (10000, 19999).

    safeexec runs each submission as a pseudo-random user id from this range,
    seeded with the time and its pid. Two grader containers have their own pid
    numbering and start runs in step, so with the same range they often pick
    the same id and share its per-user process limit (--nproc): two Java
    submissions then fail to start their threads. Giving every grader its own
    range (see docker-compose.yml) keeps them apart. Returns None if unset.
    """
    if not value:
        return None
    try:
        low, high = (int(part) for part in value.split("-"))
    except ValueError:
        raise ValueError("SAFEEXEC_UIDS must look like 10000-19999, got %r" % value)
    # The bounds safeexec itself accepts.
    if not 500 <= low <= high < 65536:
        raise ValueError(
            "SAFEEXEC_UIDS must be within 500-65535 with low <= high, got %r" % value
        )
    return low, high


def is_deadlock(error):
    """True if a database error is Postgres' "deadlock detected" (40P01)."""
    return getattr(error.__cause__, "pgcode", None) == "40P01"


def retry_on_deadlock(fn, attempts=5, delay=0.5):
    """Run fn(), running it again if Postgres aborts it with a deadlock.

    Changing a submission's result fires a database trigger that updates the
    problem's points and every user who submitted to it (db_scripts/), so
    concurrent result changes (another grader, a rejudge) can deadlock.
    Postgres rolls back one of the two transactions, which is then safe to
    run again.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except OperationalError as e:
            if not is_deadlock(e) or attempt == attempts:
                raise
            time.sleep(delay * attempt)


def update_submission(
    submission, execution_time, memory_used, result_name, judgement_details
):
    submission.execution_time = execution_time
    submission.memory_used = memory_used
    submission.result = Result.objects.get(name__iexact=result_name)
    submission.judgement_details = judgement_details
    retry_on_deadlock(submission.save)


def set_internal_error(submission, judgement_details=None):
    update_submission(submission, 0, 0, "internal error", judgement_details)


def set_compilation_error(submission, judgement_details=None):
    update_submission(submission, 0, 0, "compilation error", judgement_details)


def on_remove_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWUSR)
        func(path)
    except:
        pass


def remove_submission_folder(submission):
    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))
    if os.path.exists(submission_folder):
        shutil.rmtree(submission_folder, onerror=on_remove_error)
    return submission_folder


def create_submission_folder(submission):
    submission_folder = remove_submission_folder(submission)
    os.makedirs(submission_folder, exist_ok=True)
    return submission_folder


def check_problem_folder(problem):
    i_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), "inputs")
    o_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), "outputs")
    if not os.path.exists(i_folder) or not os.path.isdir(i_folder):
        return False
    if not os.path.exists(o_folder) or not os.path.isdir(o_folder):
        return False
    if len(os.listdir(i_folder)) != len(os.listdir(o_folder)):
        return False
    return True


def compile_checker(checker, cwd):
    from .__checker_backends import compile_checker

    return compile_checker(checker, cwd)


def compile_submission(submission):
    log.debug("Compiling submission #%d", submission.id)
    compiler = submission.compiler

    submission.result = Result.objects.get(name__iexact="compiling")
    retry_on_deadlock(submission.save)

    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))
    src_file = "%d.%s" % (submission.id, compiler.file_extension)
    exe_file = "%d.%s" % (submission.id, compiler.exec_extension)

    if compiler.language.lower() == "java":
        src_file = "Main.java"
        exe_file = "Main.class"
    elif compiler.language.lower() == "kotlin":
        src_file = "Main.kt"
        exe_file = "MainKt.class"

    with open(os.path.join(submission_folder, src_file), "wb") as f:
        f.write(submission.source.encode("utf8"))

    if compiler.language.lower() in ["python", "javascript"]:
        return True

    try:
        env = json.loads(compiler.env) if compiler.env else None
        code, out, err = get_exitcode_stdout_stderr(
            cmd='"%s" %s'
            % (compiler.path, compiler.arguments.format(src_file, exe_file)),
            cwd=submission_folder,
            env=env,
        )

        if code != 0:
            # Some error ocurred
            log.warning(
                "Compiler exited with non-zero code (%d), stdout: %s, stderr: %s",
                code,
                out,
                err,
            )

        if os.path.exists(os.path.join(submission_folder, exe_file)):
            return True

        details = ""
        details = details + out if out else details
        details = details + err if err else details
        set_compilation_error(submission, details)
    except Exception as e:
        log.error(
            "Internal error during compilation, submission: #%d, error: %s",
            submission.id,
            str(e),
        )
        set_internal_error(submission, "internal error during compilation phase")
    return False


def mark_as_running(submission: Submission):
    """Marks a submission as running"""
    submission.result = Result.objects.get(name__iexact="running")
    retry_on_deadlock(submission.save)


def get_submission_folder(submission: Submission) -> str:
    return os.path.join(settings.SANDBOX_FOLDER, str(submission.id))


def get_cmd_for_language_safeexec(
    submission: Submission,
    compiler: Compiler,
    lang: str,
    time_limit: int,
    memory_limit: int,
    uids=None,
) -> str:
    """Get language-specific command, using safeexec"""
    # note that safeexec should be in PATH, see the docker/common/make_safeexec.sh script
    # note2:we need to pipe the data directly, patching safeexec to accept --stdin/--stdout
    #   (like i did a time ago :p ) may lead to some unwanted security issues (RCE/Privilege
    #    escalation/Information diclosure) all because it uses the SUID bit
    # note3:only --cpu is the real time limit; --clock is a loose backstop (see
    #   CLOCK_LIMIT_MULTIPLIER).
    clock_limit = get_clock_limit(time_limit)
    # The user id range safeexec picks from; see parse_uids.
    safeexec = "safeexec --uids %d %d" % uids if uids else "safeexec"
    if lang == "java":
        cmd = f"{safeexec} --stack {LARGECONST} --nproc 20 --mem {memory_limit*1024} --cpu {time_limit} --clock {clock_limit} --vmrss --exec /usr/bin/java -Dfile.encoding=UTF-8 -XX:+UseSerialGC -Xms32m -Xmx{memory_limit}M -Xss64m -DMOG=true Main"
        return cmd
    elif lang == "kotlin":
        return f"{safeexec} --stack {LARGECONST} --nproc 20 --mem {memory_limit*1024} --cpu {time_limit} --clock {clock_limit} --vmrss --exec /opt/kotlin-1.7.21/bin/kotlin -Dfile.encoding=UTF-8 -J-XX:+UseSerialGC -J-Xms32M -J-Xmx{memory_limit*1024}M -J-Xss64m -J-DMOG=true MainKt"
    elif lang == "csharp":
        return f"{safeexec} --stack {LARGECONST} --nproc 6 --mem {memory_limit*1024} --cpu {time_limit} --clock {clock_limit} --vmrss --exec /usr/local/bin/mono ./{submission.id}.{compiler.exec_extension}"
    elif lang in ["python", "javascript", "python2", "python3"]:
        fmt_args = compiler.arguments.format(
            "%d.%s" % (submission.id, compiler.file_extension)
        )
        return f'{safeexec} --stack {LARGECONST} --mem {memory_limit*1024} --cpu {time_limit} --clock {clock_limit} --exec "{compiler.path}" {fmt_args}'
    else:
        # Compiled binary
        return f"{safeexec} --stack {LARGECONST} --mem {memory_limit*1024} --cpu {time_limit} --clock {clock_limit} --exec ./{submission.id}.{compiler.exec_extension}"


def get_tag_value(xml, tag_name):
    element = xml.getElementsByTagName(tag_name)[0].firstChild
    return element.nodeValue if element else None


def parse_safeexec_output(out: str) -> dict:
    invocation_verdict = "FAIL"
    exit_code = 1
    processor_user_mode_time = 0
    processor_kernel_mode_time = 0
    passed_time = 0
    consumed_memory = 0
    comment = None
    execution_time = 0

    lines = out.splitlines()
    if len(lines) == 4:
        message = lines[0].strip()

        memory_match = re.match(r"memory usage: (\d+) kbytes", lines[2].strip())
        cpu_match = re.match(r"cpu usage: (\d+(\.\d+)?) seconds", lines[3].strip())

        if "Internal Error" == message:
            invocation_verdict = "INTERNAL_ERROR"
        elif "Invalid Function" == message:
            invocation_verdict = "RUNTIME_ERROR"
        elif "Time Limit Exceeded" == message:
            invocation_verdict = "TIME_LIMIT_EXCEEDED"
        elif "Output Limit Exceeded" == message:
            invocation_verdict = "RUNTIME_ERROR"
        elif "Command terminated by signal" in message:
            invocation_verdict = "RUNTIME_ERROR"
            comment = message
        elif "Command exited with non-zero status" in message:
            invocation_verdict = "RUNTIME_ERROR"
            comment = message
        elif "Memory Limit Exceeded" == message:
            invocation_verdict = "MEMORY_LIMIT_EXCEEDED"
        elif "OK" == message:
            invocation_verdict = "SUCCESS"
            exit_code = 0

        if memory_match is not None:
            mem = int(memory_match.group(1))
            consumed_memory = mem * 1024  # KiB -> Bytes

        if cpu_match is not None:
            tme = float(cpu_match.group(1))
            millis = ceil(tme * 1000)  # Secs -> Millis
            processor_user_mode_time = millis
            processor_kernel_mode_time = millis
            passed_time = millis
            execution_time = millis

    return {
        "invocation_verdict": invocation_verdict,
        "exit_code": exit_code,
        "processor_user_mode_time": processor_user_mode_time,
        "passed_time": passed_time,
        "processor_kernel_mode_time": processor_kernel_mode_time,
        "comment": comment,
        "consumed_memory": consumed_memory,
        "execution_time": execution_time,
    }


def run_safeexec(
    cmd: str,
    input_file: str,
    submission_folder: str,
):
    """See `run_grader`"""
    with open(os.path.join(submission_folder, "output.txt"), "wb") as stdout:
        with open(os.path.join(submission_folder, input_file), "rb") as stdin:
            # Need to pipe manually
            ret, out, err = get_exitcode_stdout_stderr(
                cmd=cmd.format(
                    **{"input-file": input_file, "output-file": "output.txt"}
                ),
                cwd=submission_folder,
                stdin=stdin,
                stdout=stdout,
                user="judge",
            )

    # Check for errors
    if ret != 0:
        log.debug(
            "(Grading) Process exited with non-zero result code (code=%d) stdout=%s, stderr=%s",
            ret,
            out,
            err,
        )
    return parse_safeexec_output(err), ret, out, err


def run_grader(
    cmd: str,
    input_file: str,
    submission_folder: str,
):
    """Run a single test case in safeexec"""
    result, ret, out, err = run_safeexec(cmd, input_file, submission_folder)
    log.debug("Submission ran: %s", json.dumps(result))
    return result, ret, out or "", err or ""


def grade_submission(submission, number_of_executions, uids=None):
    log.info(f"Grading submission: %d", submission.id)
    mark_as_running(submission)

    # Extract the required data
    problem = submission.problem
    checker = problem.checker
    compiler = submission.compiler
    language = compiler.language.lower()
    submission_folder = get_submission_folder(submission)

    # The checker
    checker_command = compile_checker(checker, submission_folder)
    if not checker_command:
        log.error(
            "Could not compile checker (checker=%s, folder=%s, submission id=%d)",
            str(checker),
            submission_folder,
            submission.id,
        )
        set_internal_error(submission, "internal error compiling checker")
        return

    # The memory limits
    time_limit = problem.time_limit_for_compiler(compiler)
    memory_limit = problem.memory_limit_for_compiler(compiler)

    # Build the command
    cmd = get_cmd_for_language_safeexec(
        submission, compiler, language, time_limit, memory_limit, uids
    )
    log.debug("Run cmd: %s", cmd)

    # Input & output folders
    i_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), "inputs")
    o_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), "outputs")

    # ... and the files
    i_files = sorted(os.path.join(i_folder, name) for name in os.listdir(i_folder))
    o_files = sorted(os.path.join(o_folder, name) for name in os.listdir(o_folder))

    current_test, number_of_tests = 0, len(i_files)
    maximum_execution_time, maximum_consumed_memory = 0, 0
    judgement_details = ""
    result = "accepted"

    for input_file, answer_file in zip(i_files, o_files):
        log.debug("Running test cases: in=%s, out=%s", input_file, answer_file)
        try:
            current_test += 1

            for _ in range(number_of_executions):
                # NOTE: Setting result to accepted here is needed in
                # case we retry after a TLE/ILE judgment. As a follow
                # up, we need to revisit the logic of this section and
                # refactor to make it more readable.
                result = "accepted"
                data, _, out, err = run_grader(cmd, input_file, submission_folder)
                invocation_verdict = data["invocation_verdict"]
                exit_code = data["exit_code"]
                consumed_memory = data["consumed_memory"]
                execution_time = data["execution_time"]

                if invocation_verdict in [
                    "TIME_LIMIT_EXCEEDED",
                    "IDLENESS_LIMIT_EXCEEDED",
                ]:
                    # Log-only: a wall-clock kill looks like any other TLE.
                    cpu_limit_ms = time_limit * 1000
                    if execution_time < SUSPICIOUS_CPU_FRACTION * cpu_limit_ms:
                        log.warning(
                            "Submission #%d case #%d: %s but only used %d ms of CPU "
                            "against a %d ms limit; likely a wall-clock kill caused "
                            "by host contention rather than a slow solution",
                            submission.id,
                            current_test,
                            invocation_verdict,
                            execution_time,
                            cpu_limit_ms,
                        )
                    execution_time = cpu_limit_ms

                if invocation_verdict != "SUCCESS":
                    comment = result = {
                        "SECURITY_VIOLATION": "runtime error",
                        "MEMORY_LIMIT_EXCEEDED": "memory limit exceeded",
                        "TIME_LIMIT_EXCEEDED": "time limit exceeded",
                        "IDLENESS_LIMIT_EXCEEDED": "idleness limit exceeded",
                        "CRASH": "internal error",
                        "FAIL": "internal error",
                        "RUNTIME_ERROR": "runtime error",
                        "INTERNAL_ERROR": "internal error",
                    }[invocation_verdict]
                    if invocation_verdict in ["CRASH", "FAIL"]:
                        comment = "internal error, executing submission"
                elif exit_code != 0:
                    result = "runtime error"
                    compressed_error = compress_output_lines(err)
                    comment = ("runtime error\n\n" + compressed_error).strip()
                else:
                    rc, out, err = get_exitcode_stdout_stderr(
                        cmd=checker_command % (input_file, "output.txt", answer_file),
                        cwd=submission_folder,
                    )
                    out = out.strip()
                    err = err.strip()
                    comment = out or err
                    if rc != 0:
                        result = "wrong answer"
                if result == "internal error":
                    # Log the raw safeexec stderr (`err`). When safeexec can't
                    # run the submission (e.g. it isn't setuid-root so it fails
                    # to setgid/setuid into the `judge` user) its output isn't
                    # the expected 4-line format, parse_safeexec_output falls
                    # back to FAIL, and we land here. Without `err` this is
                    # silent and impossible to diagnose from the grader output.
                    log.error(
                        "Internal error grading submission #%d on input %s: "
                        "parsed=%s, safeexec stderr=%r",
                        submission.id,
                        input_file,
                        json.dumps(data),
                        err,
                    )
                if result not in ["time limit exceeded", "idleness limit exceeded"]:
                    break  # abort retry of the test if is not time related

            maximum_execution_time = max(maximum_execution_time, execution_time)
            maximum_consumed_memory = max(maximum_consumed_memory, consumed_memory)
            judgement_details += "Case#%d [%d bytes][%d ms]: %s\n" % (
                current_test,
                consumed_memory,
                execution_time,
                comment,
            )
        except Exception as e:
            log.error("Unexpected error running test case: %s", str(e))
            result = "internal error"
        if result != "accepted":
            break
    update_submission(
        submission,
        execution_time=maximum_execution_time,
        memory_used=maximum_consumed_memory,
        result_name=result,
        judgement_details=judgement_details,
    )


def set_pending(submission_id, sleep=5, trials=100):
    log.debug("Submission #%d -> pending", submission_id)
    success = False
    while not success and trials > 0:
        try:
            with transaction.atomic():
                submission = Submission.objects.get(pk=submission_id)
                submission.result = Result.objects.get(name__iexact="pending")
                submission.save()
            success = True
        except DatabaseError as e:
            log.error("Unexpected database error: %s", str(e))
            success = False
            trials -= 1
            time.sleep(sleep)


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "--sleep",
            type=int,
            default="5",
            help="Number of seconds to sleep between grade submissions.",
        )
        parser.add_argument(
            "--number_of_executions",
            type=int,
            default="2",
            help="Number of executions to prevent TLE",
        )

    def handle(self, *args, **options):
        verbosity = {0: log.WARN, 1: log.INFO, 2: log.DEBUG, 3: log.DEBUG}
        log.basicConfig(
            format="%(levelname)s - %(message)s",
            level=verbosity.get(options["verbosity"], log.INFO),
        )
        sleep = options.get("sleep")
        number_of_executions = options.get("number_of_executions")
        # validate input
        if sleep <= 0:
            raise CommandError("sleep argument must to be positive")
        if number_of_executions < 1:
            raise CommandError("number_of_executions must to be a positive integer")
        try:
            uids = parse_uids(os.environ.get("SAFEEXEC_UIDS"))
        except ValueError as e:
            raise CommandError(str(e))
        if uids:
            log.info("Running submissions with user ids %d-%d", *uids)
        stop = StopRequest()
        while True:
            submission = None
            try:
                # this block takes the first available pending submission and change its status to Compiling
                # this will be an atomic transaction and the select_for_update method will block the submission for
                # other graders
                # Stop signals wait until the claim is committed: a grader that
                # was asked to stop never claims another submission
                with stop.held():
                    if stop.requested:
                        break
                    with transaction.atomic():
                        # if the next line returns a submission no other process can modify it until this block is finished
                        # skip_locked=True skips pending submissions another grader has locked (it is about to mark
                        # them compiling), so several graders take different submissions instead of erroring
                        submission = (
                            Submission.objects.select_for_update(skip_locked=True)
                            .select_related("compiler", "problem")
                            .filter(result__name__iexact="pending")
                            .order_by("id")
                            .first()
                        )
                        if submission:
                            log.debug(
                                "Received submission #%d, marking as 'compiling' and proceed",
                                submission.id,
                            )
                            submission.result = Result.objects.get(
                                name__iexact="compiling"
                            )
                            submission.save()

                if submission:
                    # ready to grade the new submission
                    create_submission_folder(submission)
                    if check_problem_folder(submission.problem):
                        if compile_submission(submission):
                            grade_submission(submission, number_of_executions, uids)
                    else:
                        log.error(
                            "There was a problem with the problem folder %s for submission #%d",
                            get_submission_folder(submission),
                            submission.id,
                        )
                        set_internal_error(
                            submission, "internal error, problem not ready"
                        )
                    if not settings.DEBUG:
                        # If we're in DEBUG mode, leave the submission folder
                        # to make debugging easier.
                        remove_submission_folder(submission)
                else:
                    # we only wait if there was no submission to grade
                    time.sleep(sleep)
            except DatabaseError as e:
                # Grading failed, database error caught here
                # Possible reasons:
                # 1) The connection to the database was interrupted or could not be established
                # 2) Raise condition in a trigger in the database (TODO: Fix this raise condition)
                # TODO: Add more logs!
                log.error("Unexpected database error: %s", str(e))
                close_old_connections()
                if submission:
                    set_pending(submission.id)
        log.info("Grader stopped")
