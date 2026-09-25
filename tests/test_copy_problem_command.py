import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import override_settings

from api.models import Problem, Tag

from . import FixturedTestCase


class CopyProblemCommandTestCase(FixturedTestCase):
    def test_copies_problem_relations_and_dataset(self):
        source = self.problem1
        source.title = "Problem to copy"
        source.body = "Statement"
        source.input = "Input"
        source.output = "Output"
        source.samples = '{"sample": {"in": "1", "out": "2"}}'
        source.tags.add(Tag.objects.create(name="math"))
        source.compilers.add(self.py2)
        source.save()

        with tempfile.TemporaryDirectory() as problems_folder:
            source_folder = Path(problems_folder) / str(source.pk)
            (source_folder / "inputs").mkdir(parents=True)
            (source_folder / "outputs").mkdir()
            (source_folder / "inputs" / "1.in").write_text("1\n")
            (source_folder / "outputs" / "1.out").write_text("2\n")

            output = StringIO()
            with override_settings(PROBLEMS_FOLDER=problems_folder):
                call_command(
                    "copy_problem",
                    source.pk,
                    self.running_contest.pk,
                    stdout=output,
                )

            copied = Problem.objects.get(
                contest=self.running_contest, title=source.title
            )
            self.assertNotEqual(copied.pk, source.pk)
            self.assertEqual(copied.body, source.body)
            self.assertEqual(copied.input, source.input)
            self.assertEqual(copied.output, source.output)
            self.assertEqual(copied.samples, source.samples)
            self.assertEqual(
                list(copied.tags.order_by("pk")), list(source.tags.order_by("pk"))
            )
            self.assertEqual(
                list(copied.compilers.order_by("pk")),
                list(source.compilers.order_by("pk")),
            )
            self.assertEqual(
                (
                    Path(problems_folder) / str(copied.pk) / "inputs" / "1.in"
                ).read_text(),
                "1\n",
            )
            self.assertIn(f"Copied problem {source.pk}", output.getvalue())
