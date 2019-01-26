"""
This command adds a domain to the `disposable.json` file
and should be used as follow:

$ python manage.py dispose --domain <domain>

The <domain> value will be normalized: removing trailing
spaces and converted to lowercases.
"""

import json
import os

from django.conf import settings
from django.core.management import BaseCommand, CommandError

from api.models import User


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str, help='Domain to be disposed.')

    def handle(self, *args, **options):
        domain = (options.get('domain') or '').strip().lower()
        if not domain:
            raise CommandError('Domain is required')
        path = os.path.join(settings.BASE_DIR, 'disposable.json')
        with open(path, "r") as f:
            domains = json.load(f)
        domains.append(domain)
        with open(path, "w") as f:
            json.dump(sorted(set(domains)), f, indent=2)
            f.write('\n')
        print(
            'Domain "{}" affects {} account(s)'.format(
                domain,
                User.objects.filter(email__iendswith=domain).count()
            )
        )
