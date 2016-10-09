from optparse import make_option
from django.core.management.base import BaseCommand
from api.models import Submission


class Command(BaseCommand):
    """Rejudge a given submission

    python manage.py rejudge --submission=<id>
    """

    option_list = BaseCommand.option_list + (
        make_option('--submission', default=None, dest='submission', help='under construction'),
    )

    def handle(self, *args, **options):
        pass
