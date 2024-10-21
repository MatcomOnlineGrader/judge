"""
Utilities to execute a grader
"""
from dataclasses import dataclass
from django.conf import settings

from api.models import Submission, Compiler
RUNEXE_PATH = os.path.join(settings.RESOURCES_FOLDER, "runexe.exe")
# Globally use safeexec instead of runexe, turn off to use runexe
USE_SAFEEXEC = True

@dataclass
class GraderParams:
    """
    The grader limits
    memory_limit: The memory usage limit in kilobytes
    time_limit: The time limit (including idle time) in seconds
    """
    memory_limit: int
    time_limit: int
    submission: Submission
    compiler: Compiler

def make_interp_java(params: GraderParams) -> str:
    "Build the interpreter part"
    return f'java -Xms32M -Xmx{params.memory_limit}M -Xss64m -DMOG=true Main'

def make_interp_generic(params: GraderParams) -> str:
    "Build the interpreter part"
    return '"%s" %s' % (
        params.compiler.path,
        params.compiler.arguments.format(
            "%d.%s" % (params.submission.id, params.compiler.file_extension)
        )
    )

def make_grader_safeexec(params: GraderParams) -> str:
    "Build the grader command (without the subcommand part)"
    return 'safeexec --clock %d --cpu %d --mem %d --stdin "{input-file}" --stdout "{output-file}"'%(
        params.time_limit, params.time_limit, params.memory_limit*1024
    )

def make_grader_runexe(params: GraderParams) -> str:
    "Build the grader command (without the subcommand part)"
    return '"%s" -t %ds -m %dM -xml -i "{input-file}" -o "{output-file}"'%(
        RUNEXE_PATH, params.time_limit, params.memory_limit
    )

def make_cmd(language: str, time_limit: int, memory_limit: int, compiler: Compiler, submission: Submission) -> str:
    """
    Build the grader command
    language: Which language (in lower case), eg: java, c, python
    time_limit: The time limit in seconds (including idle time)
    memory_limit: The memory limit in MebiBytes (MiB)
    compiler: The compiler to be used
    submission: The submission to grade
    """
    params = GraderParams(memory_limit=memory_limit, time_limit=time_limit, submission=submission, compiler=compiler)
    # First, the grader
    if USE_SAFEEXEC:
        grader = make_grader_safeexec(params)
    else:
        grader = make_grader_runexe(params)
    # Now the executable segment/interpreter
    if language == "java":
        cmd = make_interp_java(params)
    elif language in ["python", "javascript", "python2", "python3"]:
        cmd = make_interp_generic(params)
    else:
        cmd = "./%d.%s" % (submission.id, compiler.exec_extension)
    return f"{grader} {cmd}"




def parse_grader_output_runexe(out: str, err: str):
    "Parse the runexe grader's output"
    def get_tag_value(xml, tag_name):
        element = xml.getElementsByTagName(tag_name)[0].firstChild
        return element.nodeValue if element else None
    
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
    return processor_user_mode_time, invocation_verdict, exit_code


def parse_grader_output_safeexec(out: str, err: str):
    "Parse the runexe grader's output"
    from json import loads
    as_json = loads(err)
    result, elapsed_time_secs, memory_usage_kiby, cpu_usage_secs = (as_json[x] for x in ["result", "elapsed_time_secs", "memory_usage_kiby", "cpu_usage_secs"])
    
    if result=="IRET":
        ext = 1 # Exit code
    else:
        ext = 0
    
    #Translate result
    codes = {
        "MLE": "MEMORY_LIMIT_EXCEEDED", #Memory limit exceeded
        "RTLE": "TIME_LIMIT_EXCEEDED", #Run time limit exceeded (aka TLE)
        "TLE": "TIME_LIMIT_EXCEEDED", #Time limit exceede
        "IRET": "CRASH", #Invalid return
        "OLE": "MEMORY_LIMIT_EXCEEDED", #???  Output limit exceeded
        "RF": "CRASH", #Invalid function
        "IE": "CRASH", #Internal error
        "OK": "SUCCESS", #OK
    }
    if result in codes:
        translated_result = codes[result]
    else:
        translated_result = "CRASH" #????

    return elapsed_time_secs, translated_result, ext


def parse_grader_output(out: str, err: str):
    "Parse the grader's output"
    if USE_SAFEEXEC:
        return parse_grader_output_safeexec(out, err)
    else:
        return parse_grader_output_runexe(out, err)


def parse_and_grade(out: str, time_limit: int, err: str, cmd: str, checker_command: str, input_file: str, answer_file: str, cwd: str, submission_folder: str, result: str) -> str:
    
    processor_user_mode_time, invocation_verdict, exit_code = parse_grader_output(out, err)
    
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
    return result