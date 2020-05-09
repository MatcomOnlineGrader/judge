import time

from django.contrib.auth.models import User
from django.utils import timezone

from api.management.commands.grader import grade_submission, create_submission_folder, check_problem_folder
from api.management.commands.populate_local_dev import populate_local_dev
from api.models import Compiler, Problem, Result, Submission, User

from . import FixturedTestCase


class GraderTestCase(FixturedTestCase):
    def setUp(self):
        # populate database with relevant data
        populate_local_dev(False, False, True)

    def submit(self, source_code, problem, compiler, number_of_executions=1):
        problem = Problem.objects.get(title=problem)
        compiler = Compiler.objects.get(name=compiler)
        result = Result.objects.get(name='Pending')
        user = User.objects.get(username='alice')
        submission = Submission(
            problem=problem, source=source_code, compiler=compiler, date=timezone.now(), result=result, user=user)
        submission.save()

        create_submission_folder(submission)
        self.assertTrue(check_problem_folder(submission.problem))
        grade_submission(submission, number_of_executions, verbose=False)

        return submission

    def check_submission(self, submission_id, expected_verdict):
        """
        Wait for submission verdict or fail otherwise
        """
        expected_verdict = Result.objects.get(name=expected_verdict)
        last_verdict = None
        for i in range(10):
            submission = Submission.objects.get(id=submission_id)
            last_verdict = submission.result
            if last_verdict.name == expected_verdict.name:
                break
            time.sleep(0.1)
        self.assertEqual(last_verdict.name, expected_verdict.name)

    def test_wrong_answer_python(self):
        submission = self.submit("", "A+B", "python")
        self.check_submission(submission.id, "Wrong Answer")

    def test_accepted_python(self):
        submission = self.submit(
            "print(sum(map(int, input().split())))", "A+B", "python")
        self.check_submission(submission.id, "Accepted")

    def test_runtime_error_python(self):
        submission = self.submit(
            "print(a)", "A+B", "python")
        self.check_submission(submission.id, "Runtime Error")

    def test_runtime_error_2_python(self):
        submission = self.submit(
            "abcdef", "A+B", "python")
        self.check_submission(submission.id, "Runtime Error")
