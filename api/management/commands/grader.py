# flake8: noqa: F841

import json
import logging as log
from math import ceil
import os
import re
import shutil
import stat
import sys
import time
from xml.dom import minidom

import colorama

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db import DatabaseError, transaction, close_old_connections

from api.models import Submission, Result, Compiler
from .__utils import compress_output_lines, get_exitcode_stdout_stderr

USE_SAFEEXEC = settings.USE_SAFEEXEC
RUNEXE_PATH = os.path.join(settings.RESOURCES_FOLDER, "runexe.exe")


def update_submission(
    submission, execution_time, memory_used, result_name, judgement_details
):
    submission.execution_time = execution_time
    submission.memory_used = memory_used
    submission.result = Result.objects.get(name__iexact=result_name)
    submission.judgement_details = judgement_details
    submission.save()


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
    submission.save()

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


def report_progress(submission, current_test, number_of_tests, result, bar_width=50):
    if USE_SAFEEXEC:
        log.debug(
            "Submission #%d -> %s (Ran %d out of %d test cases)",
            submission.id,
            result or "(unknown)",
            current_test,
            number_of_tests,
        )
    else:
        # Show on
        pct = 100 * current_test // number_of_tests
        prg = current_test * bar_width // number_of_tests
        rmg = bar_width - prg
        sys.stderr.write(
            "%d [%s%s] (%d/%d - %d%%)"
            % (submission.id, "#" * prg, " " * rmg, current_test, number_of_tests, pct)
        )
        if result != "accepted" or current_test == number_of_tests:
            color = {
                "accepted": colorama.Fore.GREEN,
                "compilation error": colorama.Fore.BLUE,
                "internal error": colorama.Fore.BLUE,
            }.get(result, colorama.Fore.RED)
            sys.stderr.write("%s [%s]%s\n" % (color, result, colorama.Style.RESET_ALL))
        else:
            sys.stderr.write("\r")


def mark_as_running(submission: Submission):
    """Marks a submission as running"""
    submission.result = Result.objects.get(name__iexact="running")
    submission.save()


def get_submission_folder(submission: Submission) -> str:
    return os.path.join(settings.SANDBOX_FOLDER, str(submission.id))


def get_cmd_for_language_safeexec(
    submission: Submission,
    compiler: Compiler,
    lang: str,
    time_limit: int,
    memory_limit: int,
) -> str:
    """Get language-specific command, using safeexec"""
    # note that safeexec should be in PATH, see the docker/common/make_safeexec.sh script
    # note2:we need to pipe the data directly, patching safeexec to accept --stdin/--stdout
    #   (like i did a time ago :p ) may lead to some unwanted security issues (RCE/Privilege
    #    escalation/Information diclosure) all because it uses the SUID bit
    # note3:Shall we consider only CPU seconds and ignore the delay caused by the syscalls?
    if lang == "java":
        # HACK(leandro): The Java VM is using a lot of resources by default. This is a temporary
        # fix to let submissions to previous problems pass with lower memory limits. We need to
        # fix this ASAP, otherwise, it’s hard to reason about all these limits.
        memory_limit = (memory_limit + 500) * 1024
        return f"safeexec --stack 0 --nproc 20 --mem {memory_limit} --cpu {time_limit} --exec /usr/bin/java -Dfile.encoding=UTF-8 -XX:+UseSerialGC -Xms32m -Xmx{memory_limit}M -Xss64m -DMOG=true Main"
    elif lang == "kotlin":
        return f"safeexec --stack 0 --nproc 20 --mem {memory_limit*1024} --cpu {time_limit} --exec /opt/kotlin-1.7.21/bin/kotlin -Dfile.encoding=UTF-8 -J-XX:+UseSerialGC -J-Xms32M -J-Xmx{memory_limit*1024}M -J-Xss64m -J-DMOG=true MainKt"
    elif lang == "csharp":
        return f"safeexec --stack 0 --nproc 6 --mem {memory_limit*1024} --cpu {time_limit} --exec /usr/local/bin/mono ./{submission.id}.{compiler.exec_extension}"
    elif lang in ["python", "javascript", "python2", "python3"]:
        fmt_args = compiler.arguments.format(
            "%d.%s" % (submission.id, compiler.file_extension)
        )
        return f'safeexec --stack 0 --mem {memory_limit*1024} --cpu {time_limit} --clock {time_limit} --exec "{compiler.path}" {fmt_args}'
    else:
        # Compiled binary
        return f"safeexec --stack 0 --mem {memory_limit*1024} --cpu {time_limit} --clock {time_limit} --exec ./{submission.id}.{compiler.exec_extension}"


def get_cmd_for_language_runexe(
    submission: Submission,
    compiler: Compiler,
    language: str,
    time_limit: int,
    memory_limit: int,
) -> str:
    """Get language specific command, using runexe instead"""

    if language == "java":
        return (
            '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" java -Xms32M -Xmx%dM -Xss64m -DMOG=true Main'
            % (RUNEXE_PATH, time_limit, memory_limit, memory_limit)
        )
    elif language == "kotlin":
        # Like Java
        return (
            '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" java -Xms32M -Xmx%dM -Xss64m -DMOG=true MainKt'
            % (RUNEXE_PATH, time_limit, memory_limit, memory_limit)
        )
    elif language in ["python", "javascript", "python2", "python3"]:
        return (
            '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" "%s" %s'
            % (
                RUNEXE_PATH,
                time_limit,
                memory_limit,
                compiler.path,
                compiler.arguments.format(
                    "%d.%s" % (submission.id, compiler.file_extension)
                ),
            )
        )
    else:
        return '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" %s' % (
            RUNEXE_PATH,
            time_limit,
            memory_limit,
            "%d.%s" % (submission.id, compiler.exec_extension),
        )


def get_cmd_for_language(
    submission: Submission,
    compiler: Compiler,
    lang: str,
    time_limit: int,
    memory_limit: int,
) -> str:
    """Get the language-specific command to execute"""
    fun = get_cmd_for_language_safeexec if USE_SAFEEXEC else get_cmd_for_language_runexe
    return fun(submission, compiler, lang, time_limit, memory_limit)


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


def run_runexe(
    cmd: str,
    input_file: str,
    submission_folder: str,
    time_limit: int,
):
    """See `run_grader`"""
    result = dict()
    ret, out, err = get_exitcode_stdout_stderr(
        cmd=cmd.format(**{"input-file": input_file, "output-file": "output.txt"}),
        cwd=submission_folder,
    )

    # Also check for errors
    if ret != 0:
        log.debug(
            "(Grading) Process exited with non-zero result code (code=%d) stdout=%s, stderr=%s",
            ret,
            out,
            err,
        )

    # Parse the runexe output
    xml = minidom.parseString(out.strip())
    invocation_verdict = get_tag_value(xml, "invocationVerdict")
    exit_code = int(get_tag_value(xml, "exitCode"))
    processor_user_mode_time = int(get_tag_value(xml, "processorUserModeTime"))
    processor_kernel_mode_time = int(get_tag_value(xml, "processorKernelModeTime"))
    passed_time = int(get_tag_value(xml, "passedTime"))
    consumed_memory = int(get_tag_value(xml, "consumedMemory"))
    comment = get_tag_value(xml, "comment") or "<blank>"

    execution_time = processor_user_mode_time
    execution_time = min(execution_time, time_limit * 1000)

    result["invocation_verdict"] = invocation_verdict
    result["exit_code"] = exit_code
    result["processor_user_mode_time"] = processor_user_mode_time
    result["processor_kernel_mode_time"] = processor_kernel_mode_time
    result["passed_time"] = passed_time
    result["consumed_memory"] = consumed_memory
    result["comment"] = comment
    result["execution_time"] = execution_time
    return result, ret, out, err


def run_safeexec(
    cmd: str,
    input_file: str,
    submission_folder: str,
    time_limit: int,
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
    time_limit: int,
):
    """Run a single test case in either runexe or safeexec, see: `USE_SAFEEXEC` global variable"""
    run_the_grader = run_safeexec if USE_SAFEEXEC else run_runexe
    result, ret, out, err = run_the_grader(
        cmd, input_file, submission_folder, time_limit
    )
    log.debug("Submission ran: %s", json.dumps(result))
    return result, ret, out or "", err or ""


def grade_submission(submission, number_of_executions):
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
    cmd = get_cmd_for_language(submission, compiler, language, time_limit, memory_limit)
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

            # parse runexe output
            for _ in range(number_of_executions):
                # NOTE: Setting result to accepted here is needed in
                # case we retry after a TLE/ILE judgment. As a follow
                # up, we need to revisit the logic of this section and
                # refactor to make it more readable.
                result = "accepted"
                data, ret, out, err = run_grader(
                    cmd, input_file, submission_folder, time_limit
                )
                invocation_verdict = data["invocation_verdict"]
                exit_code = data["exit_code"]
                consumed_memory = data["consumed_memory"]
                execution_time = data["execution_time"]

                if invocation_verdict in [
                    "TIME_LIMIT_EXCEEDED",
                    "IDLENESS_LIMIT_EXCEEDED",
                ]:
                    execution_time = time_limit * 1000

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
                if result not in ["time limit exceeded", "idleness limit exceeded"]:
                    break  # abort retry of the test if is not time related
                if result == "internal error":
                    log.error("Internal error ocurred: %s,", json.dumps(data))

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
        report_progress(
            submission=submission,
            current_test=current_test,
            number_of_tests=number_of_tests,
            result=result,
        )
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
            level=(
                log.FATAL
                if not USE_SAFEEXEC
                else verbosity.get(options["verbosity"], log.INFO)
            ),
        )
        sleep = options.get("sleep")
        number_of_executions = options.get("number_of_executions")
        # validate input
        if sleep <= 0:
            raise CommandError("sleep argument must to be positive")
        if number_of_executions < 1:
            raise CommandError("number_of_executions must to be a positive integer")
        # store compilers
        colorama.init()
        while True:
            submission = None
            try:
                # this block takes the first available pending submission and change its status to Compiling
                # this will be an atomic transaction and the select_for_update method will block the submission for
                # other graders
                with transaction.atomic():
                    # if the next line returns a submission no other process can modify it until this block is finished
                    # nowait=True means that if we try to get a pending submission that is blocked by another process
                    # we don't want to wait for it, because this submission wont be pending anymore
                    # if the submission is blocked the no_wait=True will make the method to raise an exception
                    # this exception will be captured bellow... if the submission is null nothing will happen and
                    # we will continue to the next pending submission
                    submission = (
                        Submission.objects.select_for_update(nowait=True)
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
                        submission.result = Result.objects.get(name__iexact="compiling")
                        submission.save()

                if submission:
                    # ready to grade the new submission
                    create_submission_folder(submission)
                    if check_problem_folder(submission.problem):
                        if compile_submission(submission):
                            grade_submission(submission, number_of_executions)
                    else:
                        log.error(
                            "There was a problem with the problem folder %s for submission #%d",
                            get_submission_folder(submission),
                            submission.id,
                        )
                        set_internal_error(
                            submission, "internal error, problem not ready"
                        )
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
