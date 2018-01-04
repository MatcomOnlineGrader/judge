import shlex
import subprocess


def get_exitcode_stdout_stderr(cmd, cwd):
    args = shlex.split(cmd)
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    out, err = proc.communicate()
    exitcode = proc.returncode
    return exitcode, out.decode('utf-8'), err.decode('utf-8')
