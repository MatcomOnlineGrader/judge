from django.core.management import BaseCommand

from api.models import Contest, RatingChange
from mog.ratings import set_ratings


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--dry_run", type=str, default="yes")

    def handle(self, *args, **options):
        RatingChange.objects.all().delete()
        contests = list(Contest.objects.filter(rated="True").order_by("end_date"))
        for contest in contests:
            print("Rating %s..." % contest.name)
            if set_ratings(contest):
                print("OK")
            else:
                print("Checking deltas failed!!")
                break
