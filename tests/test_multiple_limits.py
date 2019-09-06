from api.models import Contest, ROLE_CHOICES, Submission
from . import FixturedTestCase, TEST_USER_PASSWORD
from mog.templatetags import security


class MultipleLimitsTestCase(FixturedTestCase):
    def setUp(self):
        super(MultipleLimitsTestCase, self).setUp()
        # setup problem 1
        self.problem1.time_limit = 1
        self.problem1.memory_limit = 64
        self.compilers = [self.py2, self.py3, self.cpp]
        self.problem1.multiple_limits = r'{"%s": {"Time": 3, "Memory": 1024},' \
                                        r'"%s": {"Time": 2, "Memory": 1024},' \
                                        r'"%s": {"Time": 5, "Memory": 2024}}' \
                                        % (self.py2.name, self.py3.name, self.cpp.name)
        # setup problem 2
        self.problem2.time_limit = 2
        self.problem2.memory_limit = 128
        self.problem2.multiple_limits = r'{"%s": {"Time": 3},' \
                                        r'"%s": {"Memory": 1024}}' \
                                        % (self.py2.name, self.py3.name)

    def test_time_limit(self):
        self.assertTrue(self.problem1.time_limit_for_compiler(self.py2) == 3)
        self.assertTrue(self.problem1.time_limit_for_compiler(self.py3) == 2)
        self.assertTrue(self.problem1.time_limit_for_compiler(self.cpp) == 5)

    def test_memory_limit(self):
        self.assertTrue(self.problem1.memory_limit_for_compiler(self.py2) == 1024)
        self.assertTrue(self.problem1.memory_limit_for_compiler(self.py3) == 1024)
        self.assertTrue(self.problem1.memory_limit_for_compiler(self.cpp) == 2024)

    def test_missing_time(self):
        self.assertTrue(self.problem2.time_limit_for_compiler(self.py2) != self.problem2.time_limit)
        self.assertTrue(self.problem2.time_limit_for_compiler(self.py3) == self.problem2.time_limit)
        self.assertTrue(self.problem2.time_limit_for_compiler(self.cpp) == self.problem2.time_limit)

    def test_missing_memory(self):
        self.assertTrue(self.problem2.memory_limit_for_compiler(self.py2) == self.problem2.memory_limit)
        self.assertTrue(self.problem2.memory_limit_for_compiler(self.py3) != self.problem2.memory_limit)
        self.assertTrue(self.problem2.memory_limit_for_compiler(self.cpp) == self.problem2.memory_limit)

    def test_missing_limits(self):
        self.problem1.multiple_limits = None
        self.problem2.multiple_limits = ' '
        for problem in [self.problem1, self.problem2]:
            for compiler in self.compilers:
                self.assertTrue(problem.memory_limit_for_compiler(compiler) == problem.memory_limit)
                self.assertTrue(problem.time_limit_for_compiler(compiler) == problem.time_limit)

    def test_bad_limits(self):
        self.problem1.multiple_limits = '----'
        self.problem2.multiple_limits = r'{"%s": "Time"= 3, "Memory": 1024},' \
                                        r'"%s": {"Time": 2, "Memory": 1024},' \
                                        r'"%s": {"Time": 5, "Memory: 2024}}' \
                                        % (self.py2.name, self.py3.name, self.cpp.name)

        for problem in [self.problem1, self.problem2]:
            for compiler in self.compilers:
                self.assertTrue(problem.memory_limit_for_compiler(compiler) == problem.memory_limit)
                self.assertTrue(problem.time_limit_for_compiler(compiler) == problem.time_limit)
