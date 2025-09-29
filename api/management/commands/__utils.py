import shlex
import subprocess


def get_exitcode_stdout_stderr(
    cmd,
    cwd,
    env=None,
    stdin=None,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    user=None,
):
    if user:
        cmd = f"su -s /bin/ash {user} -c " + shlex.quote(cmd)
    args = shlex.split(cmd)
    proc = subprocess.Popen(
        args, stdin=stdin, stdout=stdout, stderr=stderr, cwd=cwd, env=env
    )
    out, err = proc.communicate()
    exitcode = proc.returncode
    return (
        exitcode,
        out.decode("utf-8", errors="replace") if out else "",
        err.decode("utf-8", errors="replace") if err else "",
    )


def compress_output_lines(s):
    """
    Useful to compress output from compilers that can be really long on
    compilation or runtime errors. This method will not output more than
    51 lines.
    """
    lines = (s or "").split("\n")
    if len(lines) >= 51:
        return "\n".join((*lines[:25], "...", *lines[-25:]))
    return s
