# flake8: noqa: F841

import json
import os
import shutil
import stat
import sys
import time
from xml.dom import minidom

import colorama

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db import DatabaseError, transaction, close_old_connections

from api.models import Submission, Result
from .__utils import compress_output_lines, get_exitcode_stdout_stderr


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
    os.mkdir(submission_folder)
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
    compiler = submission.compiler

    submission.result = Result.objects.get(name__iexact="compiling")
    submission.save()

    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))
    src_file = "%d.%s" % (submission.id, compiler.file_extension)
    exe_file = "%d.%s" % (submission.id, compiler.exec_extension)

    if compiler.language.lower() == "java":
        src_file = "Main.java"
        exe_file = "Main.class"

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
        if os.path.exists(os.path.join(submission_folder, exe_file)):
            return True
        details = ""
        details = details + out if out else details
        details = details + err if err else details
        set_compilation_error(submission, details)
    except:
        set_internal_error(submission, "internal error during compilation phase")
    return False


def report_progress(submission, current_test, number_of_tests, result, bar_width=50):
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


def grade_submission(submission, number_of_executions):
    submission.result = Result.objects.get(name__iexact="running")
    submission.save()

    problem = submission.problem
    checker = problem.checker
    compiler = submission.compiler
    language = compiler.language.lower()
    # compile checker
    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))

    checker_command = compile_checker(checker, submission_folder)

    if not checker_command:
        set_internal_error(submission, "internal error compiling checker")
        return

    time_limit = problem.time_limit_for_compiler(compiler)
    memory_limit = problem.memory_limit_for_compiler(compiler)

    if language == "java":
        cmd = (
            '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" java -Xms32M -Xmx%dM -Xss64m -DMOG=true Main'
            % (RUNEXE_PATH, time_limit, memory_limit, memory_limit)
        )
    elif language in ["python", "javascript", "python2", "python3"]:
        cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" "%s" %s' % (
            RUNEXE_PATH,
            time_limit,
            memory_limit,
            compiler.path,
            compiler.arguments.format(
                "%d.%s" % (submission.id, compiler.file_extension)
            ),
        )
    else:
        cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" %s' % (
            RUNEXE_PATH,
            time_limit,
            memory_limit,
            "%d.%s" % (submission.id, compiler.exec_extension),
        )

    i_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), "inputs")
    o_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), "outputs")

    i_files = sorted(os.path.join(i_folder, name) for name in os.listdir(i_folder))
    o_files = sorted(os.path.join(o_folder, name) for name in os.listdir(o_folder))

    current_test = 0
    number_of_tests = len(i_files)
    maximum_execution_time = 0
    maximum_consumed_memory = 0
    judgement_details = ""
    result = "accepted"

    for input_file, answer_file in zip(i_files, o_files):
        try:
            # parse runexe output
            def get_tag_value(xml, tag_name):
                element = xml.getElementsByTagName(tag_name)[0].firstChild
                return element.nodeValue if element else None

            current_test += 1
            for _ in range(number_of_executions):
                # NOTE: Setting result to accepted here is needed in
                # case we retry after a TLE/ILE judgment. As a follow
                # up, we need to revisit the logic of this section and
                # refactor to make it more readable.
                result = "accepted"
                _, out, err = get_exitcode_stdout_stderr(
                    cmd=cmd.format(
                        **{"input-file": input_file, "output-file": "output.txt"}
                    ),
                    cwd=submission_folder,
                )

                xml = minidom.parseString(out.strip())
                invocation_verdict = get_tag_value(xml, "invocationVerdict")
                exit_code = int(get_tag_value(xml, "exitCode"))
                processor_user_mode_time = int(
                    get_tag_value(xml, "processorUserModeTime")
                )
                processor_kernel_mode_time = int(
                    get_tag_value(xml, "processorKernelModeTime")
                )
                passed_time = int(get_tag_value(xml, "passedTime"))
                consumed_memory = int(get_tag_value(xml, "consumedMemory"))
                comment = get_tag_value(xml, "comment") or "<blank>"

                execution_time = processor_user_mode_time
                execution_time = min(execution_time, time_limit * 1000)

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
            maximum_execution_time = max(maximum_execution_time, execution_time)
            maximum_consumed_memory = max(maximum_consumed_memory, consumed_memory)
            judgement_details += "Case#%d [%d bytes][%d ms]: %s\n" % (
                current_test,
                consumed_memory,
                execution_time,
                comment,
            )
        except:
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
    success = False
    while not success and trials > 0:
        try:
            with transaction.atomic():
                submission = Submission.objects.get(pk=submission_id)
                submission.result = Result.objects.get(name__iexact="pending")
                submission.save()
            success = True
        except DatabaseError as e:
            # TODO: Add logging
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
                        submission.result = Result.objects.get(name__iexact="compiling")
                        submission.save()

                if submission:
                    # ready to grade the new submission
                    create_submission_folder(submission)
                    if check_problem_folder(submission.problem):
                        if compile_submission(submission):
                            grade_submission(submission, number_of_executions)
                    else:
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
                # TODO: Add logging
                close_old_connections()
                if submission:
                    set_pending(submission.id)
