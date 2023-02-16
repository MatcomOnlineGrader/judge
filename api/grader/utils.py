import shlex
import subprocess
import sys
from collections import namedtuple

import colorama

from api.models import Result

GraderResult = namedtuple('GraderResult', ('verdict', 'time',
                                           'memory', 'judgement_details'))

GraderPartialResult = namedtuple(
    'GraderPartialResult', ('verdict', 'memory', 'time'))

CompilerArguments = namedtuple('CompilerArguments', ('path', 'arguments', 'language',
                                                     'file_extension', 'exec_extension'))

CheckerArguments = namedtuple('CheckerArguments', ('source', 'backend'))

InteractiveArguments = namedtuple(
    'InteractiveArguments', ('source', 'is_interactive'))

GraderArguments = namedtuple('GraderArguments', ('id', 'source', 'compiler',
                                                 'checker', 'interactive', 'number_of_executions',
                                                 'time_limit', 'memory_limit', 'problem_path', 'verbose'))


IDLENESS_LIMIT_EXCEEDED = "Idleness Limit Exceeded"
INTERNAL_ERROR = "Internal Error"
COMPILATION_ERROR = "Compilation Error"
RUNTIME_ERROR = "Runtime Error"
MEMORY_LIMIT_EXCEEDED = "Memory Limit Exceeded"
TIME_LIMIT_EXCEEDED = "Time Limit Exceeded"
WRONG_ANSWER = "Wrong Answer"
ACCEPTED = "Accepted"


def get_exitcode_stdout_stderr(cmd, cwd):
    args = shlex.split(cmd)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, cwd=cwd)
    out, err = proc.communicate()
    exitcode = proc.returncode
    return exitcode, \
        out.decode('utf-8', errors='replace'), \
        err.decode('utf-8', errors='replace')


def compress_output_lines(s):
    """
    Useful to compress output from compilers that can be really long on
    compilation or runtime errors. This method will not output more than
    51 lines.
    """
    lines = (s or '').split('\n')
    if len(lines) >= 52:
        return '\n'.join((*lines[:25], '...', *lines[-25:]))
    return s


def update_submission(submission, execution_time, memory_used, result_name, judgement_details):
    submission.execution_time = execution_time
    submission.memory_used = memory_used
    submission.result = Result.objects.get(name__iexact=result_name)
    submission.judgement_details = judgement_details
    submission.save()


def set_internal_error(submission, judgement_details=None):
    update_submission(submission, 0, 0, 'internal error', judgement_details)


def compile_submission(arguments: GraderArguments):
    compiler = arguments.compiler


def report_progress(submission_id, current_test, number_of_tests, result, bar_width=50):
    pct = 100 * current_test // number_of_tests
    prg = current_test * bar_width // number_of_tests
    rmg = bar_width - prg
    sys.stderr.write(
        '%d [%s%s] (%d/%d - %d%%)' % (submission_id, '#' * prg,
                                      ' ' * rmg, current_test, number_of_tests, pct)
    )
    if result != 'accepted' or current_test == number_of_tests:
        color = {
            'accepted': colorama.Fore.GREEN,
            'compilation error': colorama.Fore.BLUE,
            'internal error': colorama.Fore.BLUE
        }.get(result, colorama.Fore.RED)
        sys.stderr.write('%s [%s]%s\n' %
                         (color, result, colorama.Style.RESET_ALL))
    else:
        sys.stderr.write('\r')
