import os
import shlex
import shutil
import subprocess
import sys
import time
from xml.dom import minidom

import colorama

from django.conf import settings
from django.core.management import BaseCommand, CommandError


from api.models import Submission, Result


def get_exitcode_stdout_stderr(cmd, cwd):
    args = shlex.split(cmd)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    out, err = proc.communicate()
    exitcode = proc.returncode
    return exitcode, out, err


def update_submission(submission, execution_time, memory_used, result_name, judgement_details):
    submission.execution_time = execution_time
    submission.memory_used = memory_used
    submission.result = Result.objects.get(name__iexact=result_name)
    submission.judgement_details = judgement_details
    submission.save()


def set_internal_error(submission, judgement_details=None):
    update_submission(submission, 0, 0, 'internal error', judgement_details)


def set_compilation_error(submission, judgement_details=None):
    update_submission(submission, 0, 0, 'compilation error', judgement_details)


def remove_submission_folder(submission):
    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))
    if os.path.exists(submission_folder):
        shutil.rmtree(submission_folder)
    return submission_folder


def create_submission_folder(submission):
    submission_folder = remove_submission_folder(submission)
    os.mkdir(submission_folder)
    return submission_folder


def check_problem_folder(problem):
    i_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'inputs')
    o_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'outputs')
    if not os.path.exists(i_folder) or not os.path.isdir(i_folder):
        return False
    if not os.path.exists(o_folder) or not os.path.isdir(o_folder):
        return False
    if len(os.listdir(i_folder)) != len(os.listdir(o_folder)):
        return False
    return True


def compile_checker(checker, cwd):
    with open(settings.TESTLIB_PATH, 'r') as f:
        testlib_content = ''.join(f.readlines())
    with open(os.path.join(cwd, 'testlib.h'), 'wb') as f:
        f.write(testlib_content)
    with open(os.path.join(cwd, 'checker.cpp'), 'wb') as f:
        f.write(checker.source)
    try:
        _, _, _ = get_exitcode_stdout_stderr('g++ checker.cpp -o checker.exe', cwd=cwd)
        if os.path.exists(os.path.join(cwd, 'checker.exe')):
            return True
    except:
        pass
    return False


def compile_submission(submission):
    submission.result = Result.objects.get(name__iexact='compiling')
    submission.save()

    compiler = submission.compiler

    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))
    src_file = '%d.%s' % (submission.id, compiler.file_extension)
    exe_file = '%d.%s' % (submission.id, compiler.exec_extension)

    if compiler.language.lower() == 'java':
        src_file = 'Main.java'
        exe_file = 'Main.class'

    with open(os.path.join(submission_folder, src_file), 'wb') as f:
        f.write(submission.source)

    if compiler.language.lower() == 'python':
        return True

    try:
        code, out, err = get_exitcode_stdout_stderr(
            cmd='"%s" %s' % (compiler.path, compiler.arguments.format(src_file, exe_file)),
            cwd=submission_folder
        )
        if os.path.exists(os.path.join(submission_folder, exe_file)):
            return True
        details = ''
        details = details + out if out else details
        details = details + err if err else details
        set_compilation_error(submission, details)
    except:
        set_internal_error(submission, 'internal error during compilation phase')
    return False


def report_progress(submission, current_test, number_of_tests, result, bar_width=50):
    pct = 100 * current_test // number_of_tests
    prg = current_test * bar_width // number_of_tests
    rmg = bar_width - prg
    sys.stderr.write(
        '%d [%s%s] (%d/%d - %d%%)' % (submission.id, '#' * prg, ' ' * rmg, current_test, number_of_tests, pct)
    )
    if result != 'accepted' or current_test == number_of_tests:
        color = {
            'accepted': colorama.Fore.GREEN,
            'compilation error': colorama.Fore.BLUE,
            'internal error': colorama.Fore.BLUE
        }.get(result, colorama.Fore.RED)
        sys.stderr.write('%s [%s]%s\n' % (color, result, colorama.Style.RESET_ALL))
    else:
        sys.stderr.write('\r')


def grade_submission(submission):
    submission.result = Result.objects.get(name__iexact='running')
    submission.save()

    problem = submission.problem
    checker = problem.checker
    compiler = submission.compiler

    # compile checker
    submission_folder = os.path.join(settings.SANDBOX_FOLDER, str(submission.id))
    if not compile_checker(checker, submission_folder):
        set_internal_error(submission, 'internal error compiling checker')
        return

    if compiler.language.lower() == 'java':
        cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" --no-idleness-check java -Xms32M -Xmx256M -DMOG=true Main'\
              % (settings.RUNEXE_PATH, problem.time_limit, problem.memory_limit)
    elif compiler.language.lower() == 'python':
        cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" --no-idleness-check "%s" %s' \
              % (settings.RUNEXE_PATH, problem.time_limit, problem.memory_limit, compiler.path, '%d.%s' % (submission.id, compiler.file_extension))
    else:
        cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" --no-idleness-check %s' \
              % (settings.RUNEXE_PATH, problem.time_limit, problem.memory_limit, '%d.%s' % (submission.id, compiler.exec_extension))

    i_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'inputs')
    o_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'outputs')

    i_files = sorted(os.path.join(i_folder, name) for name in os.listdir(i_folder))
    o_files = sorted(os.path.join(o_folder, name) for name in os.listdir(o_folder))

    current_test = 0
    number_of_tests = len(i_files)
    maximum_execution_time = 0
    maximum_consumed_memory = 0
    judgement_details = ''
    result = 'accepted'

    for input_file, answer_file in zip(i_files, o_files):
        try:
            _, out, err = get_exitcode_stdout_stderr(
                cmd=cmd.format(**{'input-file': input_file, 'output-file': 'output.txt'}),
                cwd=submission_folder
            )

            # parse runexe output
            def get_tag_value(xml, tag_name):
                element = xml.getElementsByTagName(tag_name)[0].firstChild
                return element.nodeValue if element else None

            xml = minidom.parseString(out.strip())
            invocation_verdict = get_tag_value(xml, 'invocationVerdict')
            exit_code = int(get_tag_value(xml, 'exitCode'))
            processor_user_mode_time = int(get_tag_value(xml, 'processorUserModeTime'))
            processor_kernel_mode_time = int(get_tag_value(xml, 'processorKernelModeTime'))
            passed_time = int(get_tag_value(xml, 'passedTime'))
            consumed_memory = int(get_tag_value(xml, 'consumedMemory'))
            comment = get_tag_value(xml, 'comment') or '<blank>'

            current_test += 1
            maximum_execution_time = max(maximum_execution_time, passed_time)
            maximum_consumed_memory = max(maximum_consumed_memory, consumed_memory)
            judgement_details += 'Case#%d [%d bytes][%d ms]: ' % (current_test, consumed_memory, passed_time)

            if invocation_verdict != 'SUCCESS':
                judgement_details += comment + '\n'
                result = {
                    'SECURITY_VIOLATION': 'runtime error',
                    'MEMORY_LIMIT_EXCEEDED': 'memory limit exceded',
                    'TIME_LIMIT_EXCEEDED': 'time limit exceded',
                    'IDLENESS_LIMIT_EXCEEDED': 'time limit exceded',
                    'CRASH': 'internal error',
                    'FAIL': 'internal error'
                }[invocation_verdict]
            elif exit_code != 0:
                judgement_details += 'runtime error\n'
                result = 'runtime error'
            else:
                rc, _, err = get_exitcode_stdout_stderr(
                    cmd='"%s" "%s" output.txt "%s"' % (
                        os.path.join(submission_folder, 'checker.exe'), input_file, answer_file
                    ),
                    cwd=submission_folder
                )
                judgement_details += err.strip() + '\n'
                if rc != 0:
                    result = 'wrong answer'
        except:
            result = 'internal error'
        report_progress(
            submission=submission,
            current_test=current_test,
            number_of_tests=number_of_tests,
            result=result
        )
        if result != 'accepted':
            break
    update_submission(
        submission,
        execution_time=maximum_execution_time,
        memory_used=maximum_consumed_memory,
        result_name=result,
        judgement_details=judgement_details
    )


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('--sleep', type=int, default='5', help='Number of seconds to sleep between grade submissions.')
        parser.add_argument('--number_of_graders', type=int, default='1', help='Number of graders running concurrently.')
        parser.add_argument('--grader_index', type=int, default='0', help='Grader index in the range [0, number_of_graders).')

    def handle(self, *args, **options):
        sleep, number_of_graders, grader_index = options.get('sleep'),\
                                                 options.get('number_of_graders'),\
                                                 options.get('grader_index')
        # validate input
        if sleep <= 0:
            raise CommandError('sleep argument must to be positive')
        if number_of_graders <= 0:
            raise CommandError('number_of_graders argument must to be positive')
        if not (0 <= grader_index < number_of_graders):
            raise CommandError('grader_index argument must to be in the range [0, %d)' % number_of_graders)
        # store compilers
        colorama.init()
        while True:
            for submission in Submission.objects.select_related('compiler', 'problem')\
                    .filter(result__name__iexact='pending'):
                if submission.id % number_of_graders == grader_index:
                    create_submission_folder(submission)
                    if check_problem_folder(submission.problem):
                        if compile_submission(submission):
                            grade_submission(submission)
                    else:
                        set_internal_error(submission, 'internal error, problem not ready')
                    remove_submission_folder(submission)
            time.sleep(sleep)
