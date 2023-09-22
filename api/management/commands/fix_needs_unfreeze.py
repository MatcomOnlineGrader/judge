"""
This command backfills the new created field `needs_unfreeze` for old
contests. Every contest created before "V Copa UH" (ID = 6241) will be
back-fixed to have `needs_unfreeze` set to False.

NOTE: This command should be run after the column `needs_unfreeze` is
merged in master and pushed to our prod database.
"""

from django.core.management import BaseCommand

from api.models import Contest


LAST_CONTEST_ID_TO_BACKFILL = 6241  # V Copa UH


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--dry_run", type=str, default="yes")

    def handle(self, *args, **options):
        contests = Contest.objects.filter(
            id__lte=LAST_CONTEST_ID_TO_BACKFILL, needs_unfreeze=True
        )

        backfill = options.get("dry_run") == "no"
        affected_rows = (
            contests.update(needs_unfreeze=False) if backfill else contests.count()
        )

        if backfill:
            print(
                "Succesfully set needs_unfreeze=False for {} contests".format(
                    affected_rows,
                )
            )
        else:
            print(
                "{} contests will be affected after executing:\n{}".format(
                    affected_rows,
                    "python manage.py fix_needs_unfreeze --dry_run no",
                )
            )
