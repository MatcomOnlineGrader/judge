import io
import random
import zipfile

from django.contrib import messages
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

from io import TextIOWrapper

def random_password(length=8):
    s = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    p = "".join(random.sample(s, length))
    return p


class BaylorTeam:
    def __init__(self):
        self.coach_id = ''
        self.members_id = []
        self.id = ''
        self.institution_id = ''
        self.institution_name = ''
        self.institution_short_name = ''
        self.country = ''
        self.site_id = ''
        self.name = ''
        self.status = ''

class BaylorInstitution:
    def __init__(self):
        self.name = ''
        self.short_name = ''
        self.country = ''


class ProcessImportBaylor:
    """
    This class reads and process a .tab file with the institutions' information from Baylor and updates/creates
    the corresponding institutions in th DB.
    
    zip_ref: Zip file reference that contains the .tab files
    contest_id: Contest where the teams should be registered
    prefix: Prefix to add to each team's account
    select_pending_teams: Whether create or not pending teams (default: False)
    remove_teams: Set this arguments if the existing teams should be removed (default: False)
    """
    def __init__(self, zip_ref, contest_id, prefix, select_pending_teams = False, remove_teams = False):
        self.institutions = {}
        self.baylor_institutions = {}
        self.persons = {}
        self.teams = {}
        self.groups = {}
        self.prefix = prefix
        self.contest_id = contest_id
        self.select_pending_teams = select_pending_teams
        self.remove_teams = remove_teams
        
        self.zip_ref = zip_ref
        self.school_file = None
        self.site_file = None
        self.person_file = None
        self.team_file = None
        self.team_person_file = None

        self.not_formated_password_output = ''
        self.all_password_output = ''
        self.institution_password_output = {}
        self.site_password_output = {}

    def import_institutions(self):
        print('Importing institutions')
        print('-'*30)
        with TextIOWrapper(self.zip_ref.open(self.school_file, "r"), encoding='utf-8') as f:
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
                short_name = fields[3]
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
                baylor_institution = BaylorInstitution()
                baylor_institution.name = name
                baylor_institution.short_name = short_name
                baylor_institution.country = country_names[country]
                self.baylor_institutions[icpcid] = baylor_institution

            print('Created %d institutions and updated %d institutions' % (created, updated))

    def import_sites(self):
        print('Importing sites')
        print('-'*30)
        with TextIOWrapper(self.zip_ref.open(self.site_file, "r"), encoding='utf-8') as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split('\t')
                id = fields[0]
                name = fields[1]
                self.groups[id] = name
                count += 1
            print('%d sites imported' % count)

    def import_persons(self):
        print('Importing persons')
        print('-'*30)
        with TextIOWrapper(self.zip_ref.open(self.person_file, "r"), encoding='utf-8') as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split('\t')
                id = fields[0]
                name = fields[4]
                count += 1
                self.persons[id] = name
            print('%d persons imported' % count)

    def import_teams(self):
        print('Importing teams')
        print('-'*30)
        with TextIOWrapper(self.zip_ref.open(self.team_file, "r"), encoding='utf-8') as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split('\t')
                status = fields[5]
                if not self.select_pending_teams and status != 'A':
                    continue
                
                institution_id = fields[2]
                team = BaylorTeam()
                team.id = fields[0]
                team.name = fields[1]
                team.institution_id = institution_id
                team.site_id = fields[3]
                team.status = 'pending' if status != 'A' else 'accepted'
                team.country = self.baylor_institutions[institution_id].country
                team.institution_name = self.baylor_institutions[institution_id].name
                team.institution_short_name = self.baylor_institutions[institution_id].short_name

                self.teams[team.id] = team
                count += 1
            print('%d teams imported' % count)

    def import_team_members(self):
        print('Importing team members')
        print('-'*30)
        with TextIOWrapper(self.zip_ref.open(self.team_person_file, "r"), encoding='utf-8') as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split('\t')
                person_id = fields[0]
                team_id = fields[1]
                team_role = fields[3]
                if not self.teams.get(team_id):
                    continue
                if team_role == 'CONTESTANT':
                    self.teams[team_id].members_id.append(person_id)
                    count += 1
                elif team_role == 'COACH':
                    self.teams[team_id].coach_id = person_id
                    count += 1
            print('%d team members imported' % count)

    def get_description_of_team(self, team):
        result = ''
        result += self.persons[team.coach_id] + '[c]' + '\n'
        for member_id in team.members_id:
            result += self.persons[member_id] + '\n'
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

    def handle(self):

        contest = Contest.objects.get(pk=self.contest_id)
        
        if not contest:
            raise Exception('The contest does not exist')

        self.load_files()

        self.import_institutions()
        self.import_sites()
        self.import_persons()
        self.import_teams()
        self.import_team_members()

        def key(team):
            return team.site_id, team.institution_id, team.name

        teams = sorted(self.teams.values(), key=key)

        # remove existing instances only if the remove flag is active
        # (this will prevent removing already registered guest teams)
        if self.remove_teams:
            for instance in contest.instances.all():
                if instance.submissions.all().count() == 0:
                    instance.delete()

        id = 1

        group_teams = {}
        for site_id in self.groups.keys():
            group_teams[site_id] = []
        group_teams_dict = {}

        with transaction.atomic():
            for team in teams:
                team_id = '%s%03d' % (self.prefix, id)
                mog_team = Team.objects.filter(icpcid=team.id).first()
                mog_user = User.objects.filter(username=team_id).select_related('profile').first()
                password = random_password()

                if self.remove_teams:
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

                    group_teams[team.site_id].append((team_id, password, team))
                    group_teams_dict[team_id] = (team_id, password, team)

                    mog_team.description = self.get_description_of_team(team)
                    mog_team.institution = self.institutions[team.institution_id]
                    mog_team.save()
                    id += 1
        msg = 'Registered %d teams in \'%s\' contest' % (id-1, contest.name) 
        print(msg)

        self.generate_passwords(group_teams)

        def key_username(team):
            return team[0]

        group_teams_sorted = sorted(group_teams_dict.values(), key=key_username)
        
        self.generate_not_format_passwords(group_teams_sorted)
        
        return msg

    def generate_passwords(self, group_teams):
        all_password_output = ''
        site_password_output = ''
        institution_password_output = ''
        current_institution = ''
        current_group_site = ''
        
        for site_id in self.groups.keys():
            
            if site_password_output:
                # append site_password_output to all_password_output
                all_password_output = all_password_output + site_password_output
                self.site_password_output[current_group_site] = site_password_output
                # clear site_password_output
                site_password_output = ''

            current_group_site = self.groups[site_id]

            all_password_output = all_password_output + str(current_group_site) + str('\n') + \
                str('=' * 100) + str('\n')
            teams = group_teams[site_id]

            for team_id, password, team in teams:

                if team.institution_name != current_institution:
                    if institution_password_output:
                        institution_password_output = institution_password_output + str('\n')
                        # append institution_password_output to site_password_output
                        site_password_output = site_password_output + institution_password_output
                        self.institution_password_output[current_institution] = institution_password_output
                        # clear institution_password_output
                        institution_password_output = ''

                    current_institution = team.institution_name

                    institution_password_output = institution_password_output + str(current_institution) + str('\n') + \
                        str('-' * 100) + str('\n')

                institution_password_output = institution_password_output + \
                    str('user: %s  ||  password: %s  ||  team: %s  ||  institution: %s  ||  team_status: %s\n' % \
                    (team_id, password, team.name, team.institution_short_name, team.status))
                institution_password_output = institution_password_output + str('-' * 100) + str('\n')
            
            if institution_password_output:
                institution_password_output = institution_password_output + str('\n')
                # append institution_password_output to site_password_output
                site_password_output = site_password_output + institution_password_output
                self.institution_password_output[current_institution] = institution_password_output
                # clear institution_password_output
                institution_password_output = ''
        
        if site_password_output:
            # append site_password_output to all_password_output
            all_password_output = all_password_output + site_password_output
            self.site_password_output[current_group_site] = site_password_output
            # clear site_password_output
            site_password_output = ''

        self.all_password_output = all_password_output

    def generate_not_format_passwords(self, group_teams_sorted):
        not_formated_password_output = ''
        for team_id, password, team in group_teams_sorted:
            not_formated_password_output = not_formated_password_output + str('%s||%s||%s||%s||%s||%s||%s\n' % \
                (team_id, password, team.name, team.country, team.institution_short_name, self.groups[team.site_id], team.status))
            
        self.not_formated_password_output = not_formated_password_output

    def load_files(self):
        for infofile in self.zip_ref.infolist():
            if infofile.filename == 'School.tab':
                self.school_file = infofile
            elif infofile.filename == 'Site.tab':
                self.site_file = infofile
            elif infofile.filename == 'Person.tab':
                self.person_file = infofile
            elif infofile.filename == 'Team.tab':
                self.team_file = infofile
            elif infofile.filename == 'TeamPerson.tab':
                self.team_person_file = infofile
        if not self.school_file or not self.site_file or not self.person_file \
            or not self.team_file or not self.team_person_file:
            raise Exception("Some files are missing from the loaded file.")

    def generate_zip_password(self, contest_name) -> bytes:
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w') as zipObj:
            zipObj.writestr(str('passwords_%s/allsites.txt' % contest_name), self.all_password_output)
            zipObj.writestr(str('passwords_%s/allteams.txt' % contest_name), self.not_formated_password_output)
            for site_password in self.site_password_output:
                zipObj.writestr(str('passwords_%s/sites/%s.txt' % (contest_name, site_password)), self.site_password_output[site_password])
            for institution_password in self.institution_password_output:
                zipObj.writestr(str('passwords_%s/institutions/%s.txt' % (contest_name, institution_password)), self.institution_password_output[institution_password])
        return content.getvalue()