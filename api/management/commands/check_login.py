"""
This command reads a .tab file with the institutions' information from Baylor and updates/creates
the corresponding institutions in th DB.
"""
import datetime
import os
import random

from django.core.management import BaseCommand
from django.db import transaction

from api.models import (
    Country,
    Institution,
    Contest,
    Team,
    User,
    ContestInstance
)



class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        self.institutions = {}
        self.persons = {}
        self.teams = {}
        self.groups = {}

    def add_arguments(self, parser):
        parser.add_argument('--contest', type=int, default='',
                            help='Id of the contest where the teams should be registered')

        parser.add_argument('--date', type=str, default='',
                            help='Filter by last login date >= date')

    def handle(self, *args, **options):
        str_date = options.get('date')
        contest_id = options.get('contest')

        contest = Contest.objects.get(pk=contest_id)

        if not contest:
            print('ERROR: The contest does not exist')
            return

        print('Registered %d participants' % len(contest.instances.all()))

        min_date = datetime.datetime.strptime(str_date, '%d.%m.%Y')
        print(min_date)
        teams = []
        for instance in contest.instances.all():
            if instance.team:
                last_login = None
                for profile in instance.team.profiles.all():
                    if not last_login or (profile.user.last_login and last_login < profile.user.last_login):
                        last_login = profile.user.last_login
                if not last_login or last_login.date() < min_date.date():
                    print("last login:" + (str(last_login.date()) if last_login else "----------") + "  team: " + instance.team.name)



        # output_path = os.path.join(path, 'passwords')
        #
        # for site_id in self.groups.keys():
        #     file = open(os.path.join(output_path, '%s_passwords.txt' % self.groups[site_id]), 'w+')
        #     file.write(self.groups[site_id])
        #     file.write('\n')
        #     file.write('=' * 80)
        #     file.write('\n')
        #     teams = group_teams[site_id]
        #     for name, id, password in teams:
        #         file.write('user: %s  |  password: %s  |  team: %s\n' % (id, password, name))
        #         file.write('-' * 80)
        #         file.write('\n')
        #     file.close()
