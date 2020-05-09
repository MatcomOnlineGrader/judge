from json import loads
from pathlib import Path

from django.conf import settings

from .base import BaseGrader
from .utils import (ACCEPTED, IDLENESS_LIMIT_EXCEEDED, INTERNAL_ERROR, RUNTIME_ERROR,
                    TIME_LIMIT_EXCEEDED, GraderPartialResult,
                    compress_output_lines, get_exitcode_stdout_stderr)

GRADER_PATH = Path(settings.RESOURCES_FOLDER) / 'grader.py'


class SimpleGrader(BaseGrader):
    def prepare(self, arguments):
        super().prepare(arguments)

        language = arguments.compiler.language.lower()
        compiler = arguments.compiler
        self.command = ""

        if language == 'java':
            self.command = "java -Xms32M -Xmx256M -DMOG=true Main"
        elif language in ['python', 'javascript', 'python2', 'python3']:
            self.command = '{} {}'.format(
                compiler.path,
                compiler.arguments.format('{}.{}'.format(
                    arguments.id, compiler.file_extension))
            )
        else:
            self.command = '{}.{}'.format(
                arguments.id, compiler.exec_extension)

    def run_once(self, input_file, answer_file):
        try:
            grader_command = 'python3 {} --command "{}" --input {} --output output.txt --timelimit {} --memorylimit {}'.format(
                GRADER_PATH.absolute(),
                self.command.replace('"', '\\"'),
                input_file.absolute(),
                self.arguments.time_limit * 1000,
                self.arguments.memory_limit * 1024,
            )

            _, out, err = get_exitcode_stdout_stderr(
                cmd=grader_command,
                cwd=self.submission_folder
            )

            json_result = loads(out)
            result = json_result['verdict']
            execution_time = json_result['time_used']
            consumed_memory = json_result['memory_used']

            execution_time = min(
                execution_time, self.arguments.time_limit * 1000)

            if result in [TIME_LIMIT_EXCEEDED, IDLENESS_LIMIT_EXCEEDED]:
                execution_time = self.arguments.time_limit * 1000

            if result != ACCEPTED:
                comment = result

            elif result == RUNTIME_ERROR:
                compressed_error = compress_output_lines(err)
                comment = ('Runtime Error\n\n' +
                           compressed_error).strip()

            else:
                rc, out, err = get_exitcode_stdout_stderr(
                    cmd=self.checker_command % (
                        input_file, 'output.txt', answer_file),
                    cwd=self.submission_folder
                )
                out = out.strip()
                err = err.strip()
                comment = (out or err)
                if rc != 0:
                    result = 'wrong answer'

            self.judgement_details += 'Case#%d [%d bytes][%d ms]: %s\n' % (
                self.current_test, consumed_memory, execution_time, comment
            )

            return GraderPartialResult(verdict=result, memory=consumed_memory, time=execution_time)
        except:
            return GraderPartialResult(INTERNAL_ERROR, 0, 0)
