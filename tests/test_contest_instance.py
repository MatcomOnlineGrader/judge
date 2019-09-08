from api.models import Contest, ROLE_CHOICES, Submission
from . import FixturedTestCase, TEST_USER_PASSWORD
from mog.templatetags import security


class ContestInstanceTestCase(FixturedTestCase):
    def setUp(self):
        super(ContestInstanceTestCase, self).setUp()

    def test_has_failed(self):
        for result in [self.accepted, self.wrong_answer, self.time_limit_exceeded, self.memory_limit_exceeded,
                       self.compilation_error, self.runtime_error]:
            user = self.newUser(username="user-%s" % result.name, is_active=True)
            instance = self.newContestInstance(self.running_contest, user)
            self.newSubmission(instance, user, problem=self.problem2, result=result, status='normal')
            self.assertTrue(instance.has_failed_problem(self.problem2) == result.penalty)

    def test_has_solved(self):
        user = self.newUser(username="user", is_active=True)
        instance = self.newContestInstance(self.running_contest, user)
        self.newSubmission(instance, user, problem=self.problem2, result=self.accepted, status='normal')
        self.assertTrue(instance.has_solved_problem(self.problem2))

    def test_has_failed_frozen(self):
        for result in [self.accepted, self.wrong_answer, self.time_limit_exceeded, self.memory_limit_exceeded,
                       self.compilation_error, self.runtime_error]:
            user = self.newUser(username="user-%s" % result.name, is_active=True)
            instance = self.newContestInstance(self.running_contest, user)
            self.newSubmission(instance, user, problem=self.problem2, result=result, status='frozen')
            self.assertFalse(instance.has_failed_problem(self.problem2))

    def test_has_failed_death(self):
        for result in [self.accepted, self.wrong_answer, self.time_limit_exceeded, self.memory_limit_exceeded,
                       self.compilation_error, self.runtime_error]:
            user = self.newUser(username="user-%s" % result.name, is_active=True)
            instance = self.newContestInstance(self.running_contest, user)
            self.newSubmission(instance, user, problem=self.problem2, result=result, status='death')
            self.assertFalse(instance.has_failed_problem(self.problem2))

    def test_has_solved_frozen(self):
        user = self.newUser(username="user", is_active=True)
        instance = self.newContestInstance(self.running_contest, user)
        self.newSubmission(instance, user, problem=self.problem2, result=self.accepted, status='frozen')
        self.assertFalse(instance.has_solved_problem(self.problem2))

    def test_has_solved_death(self):
        user = self.newUser(username="user", is_active=True)
        instance = self.newContestInstance(self.running_contest, user)
        self.newSubmission(instance, user, problem=self.problem2, result=self.accepted, status='death')
        self.assertFalse(instance.has_solved_problem(self.problem2))