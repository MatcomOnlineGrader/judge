from . import FixturedTestCase
from api.models import Problem


class ProblemTestCase(FixturedTestCase):
    def test_default_points_value(self):
        problem = Problem.objects.create(
            title="A*B",
            time_limit=0,
            memory_limit=0,
            position=1,
            contest=self.past_contest,
        )
        self.assertEqual(problem.points, 10)

    def test_compilers2str_lists_only_active_compilers(self):
        self.py2.active = False
        self.py2.save()
        details = self.problem1.compilers2str
        self.assertIn(self.cpp.name, details)
        self.assertIn(self.py3.name, details)
        self.assertNotIn(self.py2.name, details)
