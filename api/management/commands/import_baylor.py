"""
This command reads a .tab file with the institutions' information from Baylor and updates/creates
the corresponding institutions in th DB.
"""
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


def random_password(length=8):
    s = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    p = "".join(random.sample(s, length))
    return p


class BaylorTeam:
    def __init__(self):
        self.coach_id = ''
        self.members_id = []
        self.id = ''
        self.site_id = ''
        self.name = ''
        self.institution_id = ''


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

        self.institutions = {}
        self.persons = {}
        self.teams = {}
        self.groups = {}

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, default='',
                            help='Folder that contains the .tab files')
        parser.add_argument('--prefix', type=str, default='',
                            help='Prefix to add to each team\'s account')
        parser.add_argument('--contest', type=int, default='',
                            help='Id of the contest where the teams should be registered')
        parser.add_argument('--remove', action='store_true',
                            help='Set this arguments if the existing teams should be removed')

    def import_institutions(self, path):
        print('Importing institutions')
        print('-'*30)
        f = open(path, 'r', encoding='utf-8')
        lines = list(f.readlines())
        country_names = {'PRI': 'Puerto Rico',
                         'TTO': 'Trinidad & Tobago',
                         'JAM': 'Jamaica',
                         'DOM': 'Dominican Republic',
                         'CUB': 'Cuba'}
        created = 0
        updated = 0

        for line in lines[1:]:
            fields = line.split('\t')
            icpcid = fields[0]
            name = fields[2]
            url = fields[4]
            country = fields[5]

            institution = Institution.objects.filter(name=name).first()

            if not institution:
                institution = Institution.objects.create(name=name)
                created += 1
            else:
                updated += 1

            institution.url = url

            if country in country_names:
                institution.country = Country.objects.filter(name=country_names[country]).first()
            else:
                print('WARNING: Country %s was not found' % country)
            institution.save()
            self.institutions[icpcid] = institution

        print('Created %d institutions and updated %d institutions' % (created, updated))

    def import_sites(self, path):
        print('Importing sites')
        print('-'*30)
        f = open(path, 'r', encoding='utf-8')
        lines = list(f.readlines())
        count = 0
        for line in lines[1:]:
            fields = line.split('\t')
            id = fields[0]
            name = fields[1]
            self.groups[id] = name
            count += 1
        print('%d sites imported' % count)

    def import_persons(self, path):
        print('Importing persons')
        print('-'*30)
        f = open(path, 'r', encoding='utf-8')
        lines = list(f.readlines())
        count = 0
        for line in lines[1:]:
            fields = line.split('\t')
            id = fields[0]
            name = fields[4]
            count += 1
            self.persons[id] = name
        print('%d persons imported' % count)

    def import_teams(self, path):
        print('Importing teams')
        print('-'*30)
        f = open(path, 'r', encoding='utf-8')
        lines = list(f.readlines())
        count = 0
        for line in lines[1:]:
            fields = line.split('\t')
            status = fields[5]
            if status != 'A':
                continue

            team = BaylorTeam()
            team.id = fields[0]
            team.name = fields[1]
            team.institution_id = fields[2]
            team.site_id = fields[3]
            self.teams[team.id] = team
            count += 1
        print('%d teams imported' % count)

    def import_team_members(self, path):
        print('Importing team members')
        print('-'*30)
        f = open(path, 'r', encoding='utf-8')
        lines = list(f.readlines())
        count = 0
        for line in lines[1:]:
            fields = line.split('\t')
            person_id = fields[0]
            team_id = fields[1]
            team_role = fields[3]
            if team_role == 'CONTESTANT':
                self.teams[team_id].members_id.append(person_id)
                count += 1
            elif team_role == 'COACH':
                self.teams[team_id].coach_id = person_id
                count += 1
        print('%d team members imported' % count)

    def get_description_of_team(self, team):
        result = ''
        for member_id in team.members_id:
            result += self.persons[member_id] + '\n'
        result += self.persons[team.coach_id] + '[c]' + '\n'
        return result

    def create_user(self, username, password, institution):
        default = {
            "username": username,
            "email": username + "@mog.com"
        }
        user = User.objects.create(**default)
        user.set_password(password)
        user.profile.institution_id = institution.id
        user.profile.institution = institution
        user.profile.email_notifications = False
        user.profile.save()
        user.save()
        return user

    def register_team(self, contest, team, user, site):
        ContestInstance.objects.create(
            contest=contest,
            user=user,
            team=team,
            real=True,
            start_date=contest.start_date,
            group=site,
            render_team_description_only=True
        )

    def handle(self, *args, **options):
        path = options.get('path')
        prefix = options.get('prefix')
        contest_id = options.get('contest')
        remove_teams = options.get('remove')

        contest = Contest.objects.get(pk=contest_id)

        if not contest:
            print('ERROR: The contest does not exist')
            return

        self.import_institutions(os.path.join(path, 'School.tab'))
        self.import_sites(os.path.join(path, 'Site.tab'))
        self.import_persons(os.path.join(path, 'Person.tab'))
        self.import_teams(os.path.join(path, 'Team.tab'))
        self.import_team_members(os.path.join(path, 'TeamPerson.tab'))


        def key(team):
            return team.site_id, team.institution_id, team.name

        teams = sorted(self.teams.values(), key=key)

        for instance in contest.instances.all():
            if instance.submissions.all().count() == 0:
                instance.delete()

        id = 1

        group_teams = {}
        for site_id in self.groups.keys():
            group_teams[site_id] = []

        with transaction.atomic():
            for team in teams:
                team_id = '%s%03d' % (prefix, id)
                mog_team = Team.objects.filter(icpcid=team.id).first()
                mog_user = User.objects.filter(username=team_id).select_related('profile').first()
                password = random_password()

                if remove_teams:
                    if mog_team:
                        mog_team.delete()
                    if mog_user:
                        mog_user.delete()
                else:
                    if not mog_user:
                        mog_user = self.create_user(team_id, password, self.institutions[team.institution_id])
                    if not mog_team:
                        mog_team = Team.objects.create(name=team.name, icpcid=team.id)
                        mog_user.profile.teams.add(mog_team)

                    mog_user.set_password(password)
                    mog_user.save()
                    self.register_team(contest, team=mog_team, user=mog_user, site=self.groups[team.site_id])

                    group_teams[team.site_id].append((team.name, team_id, password))

                    mog_team.description = self.get_description_of_team(team)
                    mog_team.institution = self.institutions[team.institution_id]
                    mog_team.save()
                    id += 1
        print('Registered %d teams' % (id-1))

        output_path = os.path.join(path, 'passwords')
        if not os.path.exists(output_path):
            os.mkdir(output_path)

        for site_id in self.groups.keys():
            file = open(os.path.join(output_path, '%s_passwords.txt' % self.groups[site_id]), 'w+')
            file.write(self.groups[site_id])
            file.write('\n')
            file.write('=' * 80)
            file.write('\n')
            teams = group_teams[site_id]
            for name, id, password in teams:
                file.write('user: %s  |  password: %s  |  team: %s\n' % (id, password, name))
                file.write('-' * 80)
                file.write('\n')
            file.close()
