"Tests for graderapi.py"
from unittest import TestCase, main
from dataclasses import dataclass
from .graderapi import *

@dataclass
class CompilerStub:
    arguments: str
    path: str
    exec_extension: str
    file_extension: str

@dataclass
class SubmissionStub:
    id: int

class GeneralTests(TestCase):
    def test_basic_safeexec(self):
        USE_SAFEEXEC = True
        comp = CompilerStub(arguments="-DMOG", path="/bin/gcc", exec_extension="bin", file_extension="c")
        subm = SubmissionStub(id=123)
        cmd = make_cmd("c", 1, 2, compiler=comp, submission=subm)
        print(cmd)
        self.assertEqual(cmd, 'safeexec --clock 1 --cpu 1 --mem 2048 --stdin "{input-file}" --stdout "{output-file}" ./123.bin')

if __name__=="__main__":
    main()