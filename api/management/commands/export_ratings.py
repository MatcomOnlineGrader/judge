import csv
from django.core.management import BaseCommand

from api.models import UserProfile


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--dry_run", type=str, default="yes")

    def handle(self, *args, **options):
        users = [user for user in UserProfile.sorted_by_ratings() if user.has_rating]

        file = open("ratings.csv", "w", encoding="utf-8")
        file.write("sep=,\r\n")
        writer = csv.writer(file)

        rows = []
        for user in users:
            row = [user.user.username] + [str(user.rating)]
            rows.append(row)
        writer.writerows(rows)
