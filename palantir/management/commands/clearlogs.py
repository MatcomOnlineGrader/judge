from django.core.management import BaseCommand
from palantir.models import AccessLog


class Command(BaseCommand):
    def handle(self, *args, **options):
        AccessLog.objects.all().delete()
