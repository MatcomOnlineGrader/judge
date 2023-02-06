"""
This command copy a problem into an existing contest.
"""

import os
import shutil

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from api.models import Compiler, Contest, Problem

# python manage.py copy_problem_into_contest --contest CONTEST_ID --problem PROBLEM_ID
class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--contest", type=int, help="Target contest ID")
        parser.add_argument("--problem", type=int, help="Source problem ID")

    def handle(self, *args, **options):
        contest_id = options.get("contest")
        problem_id = options.get("problem")
        contest = Contest.objects.get(pk=contest_id)
        problem = Problem.objects.get(pk=problem_id)

        target_problem = contest.problems.filter(title=problem.title).first()
        if target_problem:
            if (
                input(
                    "Problem '{} - {}' already exists in contest, continue overwriting [y/N]? ".format(
                        target_problem.pk, target_problem.title
                    )
                )
                != "y"
            ):
                return

        print("Cloning problem [overwrite={}]".format(target_problem is not None))
        with transaction.atomic():
            # Create a clone of the problem linked to the target contest. We need to make
            # sure we're reseting all relevant variables here. I don't like the idea of
            # having to keep going back to this piece of code and considering new fields if
            # something change. This should work for now ¯\_(ツ)_/¯
            problem.pk, problem.points, problem.position, problem.contest = (
                getattr(target_problem, "pk", None),
                getattr(target_problem, "points", 0),
                getattr(target_problem, "position", contest.problems.count() + 1),
                contest,
            )
            problem.save()

            if problem.compilers.count() == 0:
                # TODO(lcastillov): We need to do this in a better way. Basically copying all
                # compilers from the source problem (if needed) and removing any extra one (?)
                for compiler in Compiler.objects.filter(problem=problem_id):
                    problem.compilers.add(compiler)

            # Copy all problem folders from the source to the new problem created.
            source_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem_id))
            target_folder = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id))
            if os.path.exists(source_folder):
                if os.path.exists(target_folder):
                    shutil.rmtree(target_folder)
                shutil.copytree(source_folder, target_folder)
