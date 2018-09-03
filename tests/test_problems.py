from django.test import TestCase

from . import FixturedTestCase
from api.models import Problem


class ProblemTestCase(FixturedTestCase):
    def test_default_points_value(self):
        problem = Problem.objects.create(
            title='A*B',
            time_limit=0,
            memory_limit=0,
            position=1,
            contest=self.past_contest
        )
        self.assertEqual(problem.points, 10)
