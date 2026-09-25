import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import Contest, Problem


class Command(BaseCommand):
    help = "Copy a problem and its dataset into another contest."

    def add_arguments(self, parser):
        parser.add_argument("problem_id", type=int, help="ID of the problem to copy")
        parser.add_argument(
            "contest_id", type=int, help="ID of the destination contest"
        )

    def handle(self, *args, **options):
        try:
            source = Problem.objects.get(pk=options["problem_id"])
        except Problem.DoesNotExist:
            raise CommandError("Problem does not exist.")

        try:
            contest = Contest.objects.get(pk=options["contest_id"])
        except Contest.DoesNotExist:
            raise CommandError("Contest does not exist.")

        source_folder = Path(settings.PROBLEMS_FOLDER) / str(source.pk)
        if not source_folder.is_dir():
            raise CommandError(f"Problem dataset does not exist: {source_folder}")

        tags = list(source.tags.all())
        compilers = list(source.compilers.all())
        destination_folder = None
        destination_existed = False

        try:
            with transaction.atomic():
                values = {
                    field.attname: getattr(source, field.attname)
                    for field in source._meta.concrete_fields
                    if not field.primary_key and field.name != "contest"
                }
                new_problem = Problem.objects.create(contest=contest, **values)
                new_problem.tags.set(tags)
                new_problem.compilers.set(compilers)

                destination_folder = Path(settings.PROBLEMS_FOLDER) / str(
                    new_problem.pk
                )
                destination_existed = destination_folder.exists()
                shutil.copytree(source_folder, destination_folder)
        except Exception as error:
            if destination_folder and not destination_existed:
                shutil.rmtree(destination_folder, ignore_errors=True)
            if isinstance(error, CommandError):
                raise
            raise CommandError(f"Could not copy problem: {error}") from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Copied problem {source.pk} to problem {new_problem.pk} "
                f"in contest {contest.pk}."
            )
        )
