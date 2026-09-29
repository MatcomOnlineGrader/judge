# flake8: noqa: F841

import contextlib
import json
import logging as log
from math import ceil
import os
import random
import re
import shutil
import signal
import stat
import subprocess
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

# Compilers run on the contestant's source, so they get the same treatment as
# the submission itself: safeexec, as an unprivileged user that can't read
# /code (settings.ini), with limits. Before this they ran as root without
# limits, so an `#include` of a root-only file echoed its lines back in the
# compilation error the contestant sees, and a pathological source could hang
# the grader.
SAFEEXEC = "/usr/local/bin/safeexec"
# Where compiles pick a user id without SAFEEXEC_UIDS: safeexec's own default
# range (5000-65535), short of isolate's box users (60000+, see isolate.cf).
SAFEEXEC_DEFAULT_UIDS = (5000, 59999)
COMPILE_CPU_LIMIT = 60  # seconds, for each compiler process
COMPILE_CLOCK_LIMIT = 120  # seconds
COMPILE_MEMORY_LIMIT = 2048  # MiB
# gcc runs cc1plus, as and ld; kotlinc and csc are scripts that start the JVM
# or Mono; and every JVM/Mono thread counts as a process too.
COMPILE_NPROC = 128
# Largest file a compiler may write. -static binaries are ~8 MiB, which is
# already safeexec's default --fsize.
COMPILE_FSIZE = 512  # MiB
# Compilers that run on a VM. They reserve far more address space than they
# use, so --space (RLIMIT_AS) would break them; the JVM caps its own heap.
VM_COMPILED_LANGUAGES = {"java", "kotlin", "csharp"}

# With `grader --isolate`, every test runs safeexec, exactly as without it, but
# inside an isolate box (https://github.com/ioi/isolate, configured in
# docker/isolate/): a filesystem with only the system, the toolchains in /opt
# and the submission's own files; no network; and a cgroup that caps the
# memory of everything the submission runs. safeexec still sets the limits
# and measures time and memory, so verdicts and timings don't change.
ISOLATE = "/usr/local/bin/isolate"
ISOLATE_SETUP = os.path.join(settings.BASE_DIR, "docker", "isolate", "setup-cgroups.sh")
ISOLATE_FIRST_UID = 60000  # first_uid in isolate.cf: box N runs as 60000+N
ISOLATE_BOXES = 1000  # num_boxes in isolate.cf
ISOLATE_META = "isolate.meta"  # isolate's report, in the submission folder
# The box's own limits, above safeexec's so they only catch what safeexec
# can't: a submission that stops or kills safeexec, or memory safeexec
# doesn't see (it only watches the process it starts).
ISOLATE_EXTRA_SECONDS = 5
ISOLATE_EXTRA_MEMORY = 64  # MiB: safeexec itself, and the output file's cache
ISOLATE_PROCESSES = 64  # safeexec and the submission; --nproc limits the latter


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


def parse_box_id(value):
    """Parse an ISOLATE_BOX value like "1": the isolate box this grader uses.

    Defaults to 0. Box N runs as user id 60000+N (docker/isolate/isolate.cf),
    so, as with SAFEEXEC_UIDS, every grader on a host needs its own.
    """
    if not value:
        return 0
    try:
        box_id = int(value)
    except ValueError:
        raise ValueError("ISOLATE_BOX must be a number, got %r" % value)
    if not 0 <= box_id < ISOLATE_BOXES:
        raise ValueError(
            "ISOLATE_BOX must be within 0-%d, got %r" % (ISOLATE_BOXES - 1, value)
        )
    return box_id


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


def kill_processes_of(uid):
    """SIGKILL every process running as `uid`.

    safeexec only kills the process it started, so a compiler that hits a
    limit leaves its children (gcc's cc1plus and ld, the JVM under kotlinc)
    running, burning the CPU the next submission is timed on. `kill -1` run as
    that user reaches all of them in one call.
    """
    subprocess.run(["kill", "-KILL", "-1"], user=uid, stderr=subprocess.DEVNULL)


def get_compile_cmd(compiler_path, arguments, language, uid, errors_file):
    """safeexec command that runs a compiler as `uid`; see COMPILE_CPU_LIMIT.

    The compiler's stderr goes to `errors_file`; safeexec's own report is
    what the command writes to stderr.
    """
    memory = COMPILE_MEMORY_LIMIT * 1024
    # --stack 0 sets no limit: compilers keep the grader's own (unlimited)
    # stack, as they had before.
    limits = (
        f"--uids {uid} {uid} --cpu {COMPILE_CPU_LIMIT} --clock {COMPILE_CLOCK_LIMIT}"
        f" --mem {memory} --vmrss --nproc {COMPILE_NPROC}"
        f" --fsize {COMPILE_FSIZE * 1024} --stack 0"
    )
    if language not in VM_COMPILED_LANGUAGES:
        # --mem only watches the process safeexec starts (the gcc driver), so
        # cap every process, cc1plus included.
        limits += f" --space {memory}"
    return f'{SAFEEXEC} {limits} --error "{errors_file}" --exec "{compiler_path}" {arguments}'


def collect_build_outputs(build_folder, submission_folder):
    """Move what the compiler wrote into the submission folder, owned by root.

    The compile user owned the build folder, so only plain files are taken (a
    symlink could point anywhere), none may replace a file already in the
    submission folder, and each gets root ownership and plain permissions.
    """
    for entry in os.scandir(build_folder):
        target = os.path.join(submission_folder, entry.name)
        if not entry.is_file(follow_symlinks=False) or os.path.lexists(target):
            continue
        os.rename(entry.path, target)
        os.chown(target, 0, 0, follow_symlinks=False)
        os.chmod(target, 0o755)
    shutil.rmtree(build_folder, onerror=on_remove_error)


def run_compiler(compiler, language, submission_folder, src_file, exe_file, uids=None):
    """Compile `src_file` into `exe_file` as an unprivileged user under safeexec.

    Returns safeexec's report (see parse_safeexec_output) and the compiler's
    output. What the compiler wrote ends up in the submission folder.
    """
    # A uid from the grader's range (see parse_uids). safeexec would pick one
    # itself; picking it here lets us kill whatever the compile leaves behind.
    uid = random.randint(*(uids or SAFEEXEC_DEFAULT_UIDS))
    build_folder = os.path.join(submission_folder, "build")
    os.mkdir(build_folder, 0o700)
    os.chown(build_folder, uid, uid)
    shutil.copyfile(
        os.path.join(submission_folder, src_file), os.path.join(build_folder, src_file)
    )

    env = json.loads(compiler.env) if compiler.env else dict(os.environ)
    # Keep the compiler's scratch files in the build folder, the only place
    # the compile user can write besides /tmp.
    env.update(HOME=build_folder, TMPDIR=build_folder)
    # safeexec starts programs with execve(), which does not search PATH, and
    # some compilers are stored by name (javac, csc).
    compiler_path = shutil.which(compiler.path, path=env.get("PATH", os.defpath))
    if not compiler_path:
        raise RuntimeError("compiler %r not found" % compiler.path)

    errors_file = os.path.join(submission_folder, "compile_errors.txt")
    cmd = get_compile_cmd(
        compiler_path,
        compiler.arguments.format(src_file, exe_file),
        language,
        uid,
        errors_file,
    )
    try:
        # safeexec switches to `uid` but never calls setgroups(), so started
        # from root the compiler would keep root's supplementary groups (gid
        # 0 among them) and could read root:root files like settings.ini
        # (750). Start it with none.
        _, out, report = get_exitcode_stdout_stderr(
            cmd, cwd=build_folder, env=env, extra_groups=[]
        )
    finally:
        kill_processes_of(uid)
    with open(errors_file, "rb") as f:
        errors = f.read().decode("utf-8", errors="replace")
    collect_build_outputs(build_folder, submission_folder)
    return report, out + errors


def compile_submission(submission, uids=None):
    log.debug("Compiling submission #%d", submission.id)
    compiler = submission.compiler
    language = compiler.language.lower()

    submission.result = Result.objects.get(name__iexact="compiling")
    retry_on_deadlock(submission.save)

    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))
    src_file = "%d.%s" % (submission.id, compiler.file_extension)
    exe_file = "%d.%s" % (submission.id, compiler.exec_extension)

    if language == "java":
        src_file = "Main.java"
        exe_file = "Main.class"
    elif language == "kotlin":
        src_file = "Main.kt"
        exe_file = "MainKt.class"

    with open(os.path.join(submission_folder, src_file), "wb") as f:
        f.write(submission.source.encode("utf8"))

    if language in ["python", "javascript"]:
        return True

    try:
        report, output = run_compiler(
            compiler, language, submission_folder, src_file, exe_file, uids
        )
        if parse_safeexec_output(report)["invocation_verdict"] in (
            "FAIL",
            "INTERNAL_ERROR",
        ):
            # safeexec couldn't run the compiler at all.
            log.error(
                "Could not run the compiler for submission #%d, safeexec: %r",
                submission.id,
                report,
            )
            set_internal_error(submission, "internal error during compilation phase")
            return False

        # First line of safeexec's report: "OK", "Command exited with non-zero
        # status (1)", or the limit that stopped the compiler.
        verdict = report.splitlines()[0].strip()
        if verdict == "OK" or verdict.startswith("Command exited"):
            if os.path.exists(os.path.join(submission_folder, exe_file)):
                return True
        else:
            log.warning(
                "Compiler for submission #%d stopped: %s", submission.id, verdict
            )
            output = (output + "\n\nCompilation stopped: %s" % verdict).strip()
        set_compilation_error(submission, output)
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


def get_cmd_for_language_isolate(
    submission: Submission,
    compiler: Compiler,
    lang: str,
    time_limit: int,
    memory_limit: int,
    box_id: int,
    meta_file: str,
) -> str:
    """get_cmd_for_language_safeexec's command, run in isolate box `box_id`
    (see ISOLATE), which writes its own report to `meta_file`.

    safeexec runs as the box's user: in a box it can't switch to another one,
    and doesn't need to. Its limits and report are exactly as without isolate;
    the box's limits are only a backstop, above them.
    """
    box_uid = ISOLATE_FIRST_UID + box_id
    safeexec = get_cmd_for_language_safeexec(
        submission, compiler, lang, time_limit, memory_limit, (box_uid, box_uid)
    )
    backstop = get_clock_limit(time_limit) + ISOLATE_EXTRA_SECONDS
    # isolate doesn't search PATH for the program; env does, and then becomes
    # safeexec.
    return (
        f"{ISOLATE} --cg --box-id={box_id} --silent --time={backstop}"
        f" --wall-time={backstop} --cg-mem={(memory_limit + ISOLATE_EXTRA_MEMORY) * 1024}"
        f" --processes={ISOLATE_PROCESSES} --dir=/opt"
        f" --env=PATH=/usr/local/bin:/usr/bin:/bin --env=HOME=/box"
        f" --meta={meta_file} --run -- /usr/bin/env {safeexec}"
    )


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
    user="judge",
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
                user=user,
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


def read_isolate_meta(meta_file: str) -> dict:
    """isolate's report (its --meta file); empty if it wrote none."""
    meta = {}
    with contextlib.suppress(FileNotFoundError):
        with open(meta_file) as f:
            meta = dict(line.rstrip("\n").split(":", 1) for line in f if ":" in line)
    return meta


def get_box_verdict(meta: dict):
    """How the isolate box stopped the run, from isolate's report: None if
    safeexec finished on its own and its report stands."""
    # Checked first: when the box's memory cap kills the submission, safeexec
    # still finishes, and reports a time limit or runtime error.
    if meta.get("cg-oom-killed"):
        return "MEMORY_LIMIT_EXCEEDED"
    status = meta.get("status")  # absent when safeexec exited with 0
    if status is None and meta.get("exitcode") == "0":
        return None
    if status == "TO":
        return "TIME_LIMIT_EXCEEDED"
    if status == "SG":
        # Nothing but the submission, running as the same user, kills
        # safeexec.
        return "RUNTIME_ERROR"
    # safeexec or isolate failed, or isolate wrote no report at all.
    return "INTERNAL_ERROR"


def cleanup_isolate_box(box_id: int):
    get_exitcode_stdout_stderr(f"{ISOLATE} --cg --box-id={box_id} --cleanup", cwd="/")


def init_isolate_box(box_id: int, files):
    """A fresh isolate box `box_id`, holding only `files`."""
    cleanup_isolate_box(box_id)
    code, out, err = get_exitcode_stdout_stderr(
        f"{ISOLATE} --cg --box-id={box_id} --init", cwd="/"
    )
    if code != 0:
        raise RuntimeError("isolate --init failed: %s" % err)
    for path in files:
        shutil.copy(path, os.path.join(out.strip(), "box"))


def run_grader(
    cmd: str,
    input_file: str,
    submission_folder: str,
    box_id=None,
    box_files=(),
):
    """Run a single test case in safeexec: inside isolate box `box_id` (see
    ISOLATE), holding the submission's `box_files`, if given"""
    if box_id is None:
        result, ret, out, err = run_safeexec(cmd, input_file, submission_folder)
    else:
        # A fresh box every run: nothing a run leaves behind reaches the next.
        init_isolate_box(box_id, box_files)
        meta_file = os.path.join(submission_folder, ISOLATE_META)
        with contextlib.suppress(FileNotFoundError):
            os.remove(meta_file)  # Never read the previous run's report.
        # safeexec already runs as the box's user; its report reaches
        # isolate's stderr.
        result, ret, out, err = run_safeexec(
            cmd, input_file, submission_folder, user=None
        )
        meta = read_isolate_meta(meta_file)
        box_verdict = get_box_verdict(meta)
        if box_verdict:
            result.update(
                invocation_verdict=box_verdict,
                exit_code=1,
                execution_time=ceil(float(meta.get("time", 0)) * 1000),
                consumed_memory=int(meta.get("cg-mem", 0)) * 1024,  # KiB
            )
    log.debug("Submission ran: %s", json.dumps(result))
    return result, ret, out or "", err or ""


def grade_submission(submission, number_of_executions, uids=None, box_id=None):
    """Grade under safeexec: inside isolate box `box_id` (see ISOLATE), or
    with user ids from `uids` if it's None."""
    log.info(f"Grading submission: %d", submission.id)
    mark_as_running(submission)

    # Extract the required data
    problem = submission.problem
    checker = problem.checker
    compiler = submission.compiler
    language = compiler.language.lower()
    submission_folder = get_submission_folder(submission)

    # What an isolate box gets: the submission's source and what the compiler
    # made. Listed now, before the checker's files join them.
    box_files = [
        entry.path
        for entry in os.scandir(submission_folder)
        if entry.is_file(follow_symlinks=False) and entry.name != "compile_errors.txt"
    ]

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
    # int(): per-compiler limits come from free-form JSON and may be strings.
    memory_limit = int(problem.memory_limit_for_compiler(compiler))

    # Build the command
    if box_id is None:
        cmd = get_cmd_for_language_safeexec(
            submission, compiler, language, time_limit, memory_limit, uids
        )
    else:
        meta_file = os.path.join(submission_folder, ISOLATE_META)
        cmd = get_cmd_for_language_isolate(
            submission, compiler, language, time_limit, memory_limit, box_id, meta_file
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
                data, _, out, err = run_grader(
                    cmd, input_file, submission_folder, box_id, box_files
                )
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
        parser.add_argument(
            "--isolate",
            action="store_true",
            help="Run safeexec inside isolate box ISOLATE_BOX (default 0). "
            "See ISOLATE in grader.py.",
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
        box_id = None
        if options["isolate"]:
            # Graders on the same host need different boxes: a box's user id
            # (and its process limit) is shared across containers.
            try:
                box_id = parse_box_id(os.environ.get("ISOLATE_BOX"))
            except ValueError as e:
                raise CommandError(str(e))
            code, out, err = get_exitcode_stdout_stderr(
                f"sh {ISOLATE_SETUP}", cwd=settings.BASE_DIR
            )
            if code != 0:
                raise CommandError("Could not set up cgroups for isolate: %s" % err)
            log.info("Running submissions in isolate box %d", box_id)
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
                        if compile_submission(submission, uids):
                            grade_submission(
                                submission, number_of_executions, uids, box_id
                            )
                            if box_id is not None:
                                cleanup_isolate_box(box_id)
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
