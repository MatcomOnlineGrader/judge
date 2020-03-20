from django.urls import reverse

from . import FixturedTestCase
from api.models import Problem
from mog.gating import grant_role_to_user_in_contest


class ContestTestCase(FixturedTestCase):
    def test_create_problem_in_contest(self):
        """Test that a user can create a problem in a contest where they
        have the role of judge."""
        judge, contest = self.newLoggedUser(username='judge'), \
            self.newContest()
        grant_role_to_user_in_contest(judge, contest, 'judge')
        url = reverse('mog:contest_create_problem', args=(contest.pk, ))
        self.client.post(url, data=self._get_problem_form_data())
        problems = Problem.objects.filter(contest__id=contest.pk)
        self.assertEqual(1, len(problems))

    def test_judge_cannot_create_problem_in_contest(self):
        """Test that a user cannot create a problem in a contest where
        they don't have the role of judge."""
        judge, contest, other_contest = self.newLoggedUser(username='judge'), \
            self.newContest(code='c1'), self.newContest(code='c2')
        grant_role_to_user_in_contest(judge, contest, 'judge')
        url = reverse('mog:contest_create_problem', args=(other_contest.pk, ))
        response = self.client.post(url, data=self._get_problem_form_data())
        self.assertEqual(404, response.status_code)

    def _get_problem_form_data(self):
        return {
            'title': 'A+B',
            'body': 'Find the sum of two numbers',
            'input': 'One line: A B',
            'output': 'One line: A+B',
            'time_limit': 3,
            'memory_limit': 128,
            'checker': self.wcmp.id,
            'position': 1,
            'letter_color': '#ffffff',
            'compilers': [self.py2.id]
        }
