import os
from xml.dom import minidom
from pathlib import Path

from django.conf import settings

from .base import BaseGrader
from .utils import (ACCEPTED, IDLENESS_LIMIT_EXCEEDED, INTERNAL_ERROR, MEMORY_LIMIT_EXCEEDED,
                    RUNTIME_ERROR, TIME_LIMIT_EXCEEDED, WRONG_ANSWER,
                    GraderPartialResult, compress_output_lines,
                    get_exitcode_stdout_stderr)

RUNEXE_PATH = Path(settings.RESOURCES_FOLDER) / 'runexe.exe'


def get_tag_value(xml, tag_name):
    """
    Parse runexe output
    """
    element = xml.getElementsByTagName(tag_name)[0].firstChild
    return element.nodeValue if element else None


class RunexeGrader(BaseGrader):
    @classmethod
    def check_supported(cls):
        import platform
        system = platform.system()
        if system != "Windows":
            raise Exception(
                "Invalid platform <{}>. Runexe is only available on Windows.".format(system))

    def prepare(self, arguments):
        super().prepare(arguments)

        language = arguments.compiler.language.lower()
        compiler = arguments.compiler

        if language == 'java':
            self.cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" java -Xms32M -Xmx1024M -Xss64M -DMOG=true Main'\
                % (RUNEXE_PATH, arguments.time_limit, arguments.memory_limit)
        elif language in ['python', 'javascript', 'python2', 'python3']:
            self.cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" "%s" %s' \
                % (RUNEXE_PATH, arguments.time_limit, arguments.memory_limit, compiler.path,
                    compiler.arguments.format('%d.%s' % (arguments.id, compiler.file_extension)))
        else:
            self.cmd = '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}" %s' \
                % (RUNEXE_PATH, arguments.time_limit, arguments.memory_limit, '%d.%s' %
                    (arguments.id, compiler.exec_extension))

    def run_once(self, input_file, answer_file):
        try:
            result = ACCEPTED

            _, out, err = get_exitcode_stdout_stderr(
                cmd=self.cmd.format(
                    **{'input-file': input_file, 'output-file': 'output.txt'}),
                cwd=self.submission_folder
            )

            xml = minidom.parseString(out.strip())
            invocation_verdict = get_tag_value(
                xml, 'invocationVerdict')
            exit_code = int(get_tag_value(xml, 'exitCode'))
            processor_user_mode_time = int(
                get_tag_value(xml, 'processorUserModeTime'))
            processor_kernel_mode_time = int(
                get_tag_value(xml, 'processorKernelModeTime'))
            passed_time = int(get_tag_value(xml, 'passedTime'))
            consumed_memory = int(get_tag_value(xml, 'consumedMemory'))
            comment = get_tag_value(xml, 'comment') or '<blank>'

            execution_time = processor_user_mode_time
            execution_time = min(
                execution_time, self.arguments.time_limit * 1000)

            if invocation_verdict in ['TIME_LIMIT_EXCEEDED', 'IDLENESS_LIMIT_EXCEEDED']:
                execution_time = self.arguments.time_limit * 1000

            if invocation_verdict != 'SUCCESS':
                comment = result = {
                    'SECURITY_VIOLATION': RUNTIME_ERROR,
                    'MEMORY_LIMIT_EXCEEDED': MEMORY_LIMIT_EXCEEDED,
                    'TIME_LIMIT_EXCEEDED': TIME_LIMIT_EXCEEDED,
                    'IDLENESS_LIMIT_EXCEEDED': IDLENESS_LIMIT_EXCEEDED,
                    'CRASH': INTERNAL_ERROR,
                    'FAIL': INTERNAL_ERROR
                }[invocation_verdict]
                if invocation_verdict in ['CRASH', 'FAIL']:
                    comment = 'internal error, executing submission'
            elif exit_code != 0:
                result = RUNTIME_ERROR
                compressed_error = compress_output_lines(err)
                comment = ('runtime error\n\n' +
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
                    result = WRONG_ANSWER

            self.judgement_details += 'Case#%d [%d bytes][%d ms]: %s\n' % (
                self.current_test, consumed_memory, execution_time, comment
            )

            return GraderPartialResult(verdict=result, memory=consumed_memory, time=execution_time)
        except:
            return GraderPartialResult(INTERNAL_ERROR, 0, 0)
