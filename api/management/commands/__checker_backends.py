import os
import shutil
from django.conf import settings

from .__utils import get_exitcode_stdout_stderr


def compile_checker_testlib_h(checker, cwd):
    shutil.copyfile(
        os.path.join(settings.RESOURCES_FOLDER, 'testlib.h'), os.path.join(cwd, 'testlib.h')
    )
    with open(os.path.join(cwd, 'checker.cpp'), 'wb') as f:
        f.write(checker.source.encode('utf8'))
    try:
        _, _, _ = get_exitcode_stdout_stderr('g++ checker.cpp -o checker.exe', cwd=cwd)
        if os.path.exists(os.path.join(cwd, 'checker.exe')):
            cmd = '"{0}" "%s" "%s" "%s"'.format(
                os.path.join(cwd, 'checker.exe')
            )
            return cmd
    except:
        pass


def compile_checker_testlib4j_jar(checker, cwd):
    shutil.copyfile(
        os.path.join(settings.RESOURCES_FOLDER, 'testlib4j.jar'), os.path.join(cwd, 'testlib4j.jar')
    )
    with open(os.path.join(cwd, 'Check.java'), 'wb') as f:
        f.write(checker.source.encode('utf8'))
    try:
        _, _, _ = get_exitcode_stdout_stderr('javac -classpath testlib4j.jar Check.java', cwd=cwd)
        if os.path.exists(os.path.join(cwd, 'Check.class')):
            cmd = 'java -cp "{0}";"{1}" ru.ifmo.testlib.CheckerFramework Check "%s" "%s" "%s"'.format(
                cwd, os.path.join(cwd, 'testlib4j.jar')
            )
            return cmd
    except:
        pass


def compile_checker(checker, cwd):
    """
    Compiles the corresponding checker and return the command to
    test input/output/answer for every test case.
    """
    if checker.backend == 'testlib.h':
        return compile_checker_testlib_h(checker, cwd)
    elif checker.backend == 'testlib4j.jar':
        return compile_checker_testlib4j_jar(checker, cwd)
