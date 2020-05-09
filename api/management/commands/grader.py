import os
import shutil
import stat
import time
from pathlib import Path

import colorama
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections, transaction

from api.grader import GRADERS, BaseGrader, GraderArguments
from api.grader.utils import (CheckerArguments, CompilerArguments,
                              InteractiveArguments, compress_output_lines,
                              get_exitcode_stdout_stderr, set_internal_error,
                              update_submission)
from api.models import Result, Submission

try:
    GRADER = GRADERS[settings.GRADER_ID.lower()]
except KeyError:
    print("Grader <{}> not found. Available graders are:".format(
        settings.GRADER_ID.lower()))
    for grader_name in GRADERS.keys():
        print(grader_name)
    exit(1)

GRADER.check_supported()


def on_remove_error(func, path, exc_info):
    try:
        os.chmod(path, stat.S_IWUSR)
        func(path)
    except:
        pass


def remove_submission_folder(submission):
    submission_folder = os.path.join(
        settings.SANDBOX_FOLDER, str(submission.id))
    if os.path.exists(submission_folder):
        shutil.rmtree(submission_folder, onerror=on_remove_error)
    return submission_folder


def create_submission_folder(submission):
    submission_folder = remove_submission_folder(submission)
    os.makedirs(submission_folder, exist_ok=True)
    return submission_folder


def check_problem_folder(problem):
    i_folder = os.path.join(settings.PROBLEMS_FOLDER,
                            str(problem.id), 'inputs')
    o_folder = os.path.join(settings.PROBLEMS_FOLDER,
                            str(problem.id), 'outputs')
    if not os.path.exists(i_folder) or not os.path.isdir(i_folder):
        return False
    if not os.path.exists(o_folder) or not os.path.isdir(o_folder):
        return False
    if len(os.listdir(i_folder)) != len(os.listdir(o_folder)):
        return False
    return True


def to_compiler_arguments(compiler):
    return CompilerArguments(path=compiler.path, arguments=compiler.arguments,
                             language=compiler.language, file_extension=compiler.file_extension,
                             exec_extension=compiler.exec_extension)


def to_checker_arguments(checker):
    return CheckerArguments(source=checker.source, backend=checker.backend)


def to_interactive_arguments(problem):
    return InteractiveArguments(source=None, is_interactive=False)


def update_submission_with_result(submission, result):
    update_submission(
        submission,
        execution_time=result.time,
        memory_used=result.memory,
        result_name=result.verdict,
        judgement_details=result.judgement_details
    )


def grade_submission(submission, number_of_executions, verbose=True):
    grader = GRADER()
    problem = submission.problem
    checker = problem.checker
    compiler = submission.compiler
    language = compiler.language.lower()

    arguments = GraderArguments(id=submission.id,
                                source=submission.source,
                                compiler=to_compiler_arguments(compiler),
                                checker=to_checker_arguments(checker),
                                interactive=to_interactive_arguments(problem),
                                number_of_executions=number_of_executions,
                                time_limit=problem.time_limit_for_compiler(
                                    compiler),
                                memory_limit=problem.memory_limit_for_compiler(
                                    compiler),
                                problem_path=Path(
                                    settings.PROBLEMS_FOLDER) / str(problem.id),
                                verbose=verbose)

    # Compile submission
    submission.result = Result.objects.get(name__iexact='compiling')
    submission.save()
    # If everything goes good returns None, otherwise returns Result with details
    result = grader.compile(arguments)

    if result is not None:
        # Update submission and finish
        return update_submission_with_result(submission, result)

    # Run submission
    submission.result = Result.objects.get(name__iexact='running')
    submission.save()
    result = grader.run(arguments)
    update_submission_with_result(submission, result)


def set_pending(submission_id, sleep=5, trials=100):
    success = False
    while not success and trials > 0:
        try:
            with transaction.atomic():
                submission = Submission.objects.get(pk=submission_id)
                submission.result = Result.objects.get(name__iexact='pending')
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
        parser.add_argument('--sleep', type=int, default='5',
                            help='Number of seconds to sleep between grade submissions.')
        parser.add_argument('--number_of_executions', type=int, default='2',
                            help='Number of executions to prevent TLE')

    def handle(self, *args, **options):
        sleep = options.get('sleep')
        number_of_executions = options.get('number_of_executions')
        # validate input
        if sleep <= 0:
            raise CommandError('sleep argument must to be positive')
        if number_of_executions < 1:
            raise CommandError(
                'number_of_executions must to be a positive integer')
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
                    submission = Submission.objects.select_for_update(nowait=True)\
                        .select_related('compiler', 'problem')\
                        .filter(result__name__iexact='pending').order_by('id').first()
                    if submission:
                        submission.result = Result.objects.get(
                            name__iexact='compiling')
                        submission.save()

                if submission:
                    # ready to grade the new submission
                    create_submission_folder(submission)
                    if check_problem_folder(submission.problem):
                        grade_submission(submission, number_of_executions)
                    else:
                        set_internal_error(
                            submission, 'internal error, problem not ready')
                    remove_submission_folder(submission)
                else:
                    # we only wait if there was no submission to grade
                    time.sleep(sleep)
            except:
                # Grading failed, database error caught here
                # Possible reasons:
                # 1) The connection to the database was interrupted or could not be established
                # 2) Raise condition in a trigger in the database (TODO: Fix this raise condition)
                # TODO: Add logging
                close_old_connections()
                if submission:
                    set_pending(submission.id)
