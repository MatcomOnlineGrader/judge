import os
from pathlib import Path
from typing import Optional

from django.conf import settings

from .checker_backends import compile_checker
from .utils import (ACCEPTED, COMPILATION_ERROR, IDLENESS_LIMIT_EXCEEDED, INTERNAL_ERROR,
                    TIME_LIMIT_EXCEEDED, GraderArguments, GraderPartialResult,
                    GraderResult, get_exitcode_stdout_stderr, report_progress)


class BaseGrader:
    """
    Cycle of the grader is as follows:

    1. First all arguments are gathered at `grade_submission`:

    2. Then the submission is compiled (only the submission, not extra files) with:
        ```
        grader.compile(arguments)
        ```

    3. The grader starts grading this submission.
        ```
        grader.run(arguments)
        ```

        This in itself is subdivided in two stages:

        3.1 Prepare extra sources.
            ```
            grader.prepare(arguments)
            ```

        3.2 Run submission against all testcases.
            ```
            grader.run_all()
            ```

            Run all will call `run_once(input_file, answer_file)`.
            - input_file: $PROBLEM/inputs/1.in
            - output_file: $PROBLEM/outputs/1.out
    """
    @classmethod
    def check_supported(cls):
        """
        Determine if the grader is supported for the current platform.
        Raise an error with relevant message otherwise.
        """

    def compile(self, arguments: GraderArguments) -> Optional[GraderResult]:
        """
        Compile submission.

        Return None if everything went fine, otherwise return Result with details.
        """
        # Path to create all files related to this submission.
        self.submission_folder = Path(
            settings.SANDBOX_FOLDER) / str(arguments.id)

        self.source_file = '%d.%s' % (
            arguments.id, arguments.compiler.file_extension)

        self.exec_file = '%d.%s' % (
            arguments.id, arguments.compiler.exec_extension)

        if arguments.compiler.language.lower() == 'java':
            self.source_file = 'Main.java'
            self.exec_file = 'Main.class'

        with open(self.submission_folder / self.source_file, 'wb') as f:
            f.write(arguments.source.encode('utf8'))

        if arguments.compiler.language.lower() in ['python', 'javascript']:
            return None

        try:
            code, out, err = get_exitcode_stdout_stderr(
                cmd='"%s" %s' % (
                    arguments.compiler.path, arguments.compiler.arguments.format(self.source_file, self.exec_file)),
                cwd=self.submission_folder
            )

            if (self.submission_folder / self.exec_file).exists():
                return None

            details = ''
            details = details + out if out else details
            details = details + err if err else details
            return GraderResult(verdict=COMPILATION_ERROR, time=0, memory=0, judgement_details=details)
        except:
            return GraderResult(verdict=INTERNAL_ERROR, time=0, memory=0, judgement_details='Internal error during compilation phase')

    def prepare(self, arguments: GraderArguments):
        """
        This function is always called before running the solution.
        It is used to compile all required files and make all necessary precomputations
        before starting judging each testcase.
        """
        self.arguments = arguments
        self.preparation_failed = False
        self.failure_details = None
        # Details used in case submission is Accepted
        self.judgement_details = ''

        # Compile the checker
        self.checker_command = compile_checker(
            arguments.checker, self.submission_folder)
        if not self.checker_command:
            return self.preparation_failed_with("Error compiling checker")

        self.problem_folder = arguments.problem_path
        self.input_folder = self.problem_folder / 'inputs'
        self.output_folder = self.problem_folder / 'outputs'

        if not self.input_folder.exists() or not self.output_folder.exists():
            return self.preparation_failed_with("Testcases folder doesn't exists")

        self.input_files = sorted(
            self.input_folder / name for name in os.listdir(self.input_folder))

        self.output_files = sorted(
            self.output_folder / name for name in os.listdir(self.output_folder))

        # Check there is a no empty set of testcases, where every .in file is paired
        # with a .out file with exactly the same name
        if len(self.input_files) != len(self.output_files):
            return self.preparation_failed_with("Inconsistent testcases")

        if len(self.input_files) == 0:
            return self.preparation_failed_with("No available testcases")

    def failed_with(self, failure_details):
        self.failure_details = failure_details

    def preparation_failed_with(self, failure_details):
        self.preparation_failed = True
        self.failed_with(failure_details)

    def run_once(self, input_file, answer_file) -> GraderPartialResult:
        raise NotImplementedError("Function not implemented")

    def run_all(self) -> GraderResult:
        """
        Run all testcases
        """
        if self.preparation_failed:
            return GraderResult(verdict=INTERNAL_ERROR, time=0, memory=0, judgement_details=self.failure_details)

        number_of_tests = len(self.input_files)

        maximum_execution_time = 0
        maximum_consumed_memory = 0
        result = ACCEPTED

        for current_test, (input_file, answer_file) in enumerate(zip(self.input_files, self.output_files)):
            self.current_test = current_test + 1

            # Evaluate testcase
            for _ in range(self.arguments.number_of_executions):
                partial_result = self.run_once(input_file, answer_file)
                if partial_result.verdict not in [TIME_LIMIT_EXCEEDED, IDLENESS_LIMIT_EXCEEDED]:
                    break

            # Aggregates partial results
            result = partial_result.verdict
            maximum_execution_time = max(
                partial_result.time, maximum_execution_time)
            maximum_consumed_memory = max(
                partial_result.memory, maximum_consumed_memory)

            # Pretty print progress
            if self.arguments.verbose:
                report_progress(
                    submission_id=self.arguments.id,
                    current_test=self.current_test,
                    number_of_tests=number_of_tests,
                    result=result
                )

            # Fast break in case of any failures
            if result != ACCEPTED:
                break

        return GraderResult(verdict=result, time=maximum_execution_time, memory=maximum_consumed_memory, judgement_details=self.judgement_details)

    def run(self, arguments: GraderArguments) -> GraderResult:
        """
        Prepare the environment before running a submission, and
        then run against all testcases.
        """
        self.prepare(arguments)
        return self.run_all()
