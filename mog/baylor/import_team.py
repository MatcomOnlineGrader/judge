import csv

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from api.models import (
    Institution,
    Contest,
    Team,
    User,
    ContestInstance
)

from mog.baylor.utils import generate_secret_password, hash_string, ICPCID_GUEST_PREFIX


class TeamData:
    def __init__(self):
        self.team_name = ''
        self.institution = ''
        self.coach = ''
        self.participant1 = ''
        self.participant2 = ''
        self.participant3 = ''
        self.group = ''
        self.hash = ''


class ProcessImportTeam:
    """
    This class reads and process the csv file. On every row its suppose to be a team with all information like:
    team_name: Nombre del equipo
    institution: Institución representada
    coach: Nombre coach/representante
    participant1: C1 - Nombre completo
    participant2: C2 - Nombre completo
    participant3: C3 - Nombre completo
    group: Grupo (Guest_Teams, Preuniversity_Teams)
    
    csv_ref: Csv file reference that contains the team information
    contest_id: Contest where the teams should be registered
    prefix: Prefix to add to each team's account
    """
    def __init__(self, csv_ref, contest_id, prefix):
        self.institutions = {}
        self.teams = []
        self.prefix = prefix
        self.contest_id = contest_id
        
        self.csv_ref = csv_ref
        self.csv_mapped = None

        self.messages = []


    def import_institutions(self):
        count = 0
        for line in self.csv_mapped[1:]:
            inst = line[1]
            name = inst.split(" (")[0]
            institution = Institution.objects.filter(name=name).first()
            if not institution:
                self.messages.append({'type': 'warning', 'message': _('WARNING: Institution <b>%s</b> was not found' % name) })
            else: count += 1
            self.institutions[name] = institution
        self.messages.append({'type': 'success', 'message': 'Loaded %d institutions' % count })


    def import_team_members(self):
        count = 0
        for line in self.csv_mapped[1:]:
            team = TeamData()
            team.team_name = line[0]
            inst = line[1]
            team.institution = inst.split(" (")[0]
            team.coach = line[2]
            team.participant1 = line[3]
            team.participant2 = line[4]
            team.participant3 = line[5]
            team.group = line[6]
            team.hash = hash_string(','.join(line))
            self.teams.append(team)
            count += 1
        self.messages.append({'type': 'success', 'message': 'Loaded %d teams' % count })


    def get_description_of_team(self, team: TeamData):
        result = ''
        if team.coach:
            result += team.coach + '[c]' + '\n'
        if team.participant1:
            result += team.participant1 + '\n'
        if team.participant2:
            result += team.participant2 + '\n'
        if team.participant3:
            result += team.participant3 + '\n'
        return result


    def create_user(self, username, password, institution):
        default = {
            "username": username,
            "email": username + "@mog.com"
        }
        user = User.objects.create(**default)
        user.set_password(password)
        user.profile.institution_id = institution.id if institution else None
        user.profile.institution = institution
        user.profile.email_notifications = False
        user.profile.save()
        user.save()
        return user


    def register_team(self, contest, team, site):
        ContestInstance.objects.create(
            contest=contest,
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

        self.csv_mapped = list(csv.reader(self.csv_ref))
        self.import_institutions()
        self.import_team_members()

        teams = sorted(self.teams, key=lambda x: (x.group, x.institution, x.team_name))

        id = 1

        with transaction.atomic():
            for team in teams:
                team_id = '%s_GUEST_%03d' % (self.prefix, id)
                guestid = '%s%s' % (ICPCID_GUEST_PREFIX, team.hash)
                mog_team = Team.objects.filter(icpcid=guestid).first()
                mog_user = User.objects.filter(username=team_id).select_related('profile').first()
                password = ''

                if not mog_user:
                    mog_user = self.create_user(team_id, password, self.institutions[team.institution])
                if not mog_team:
                    mog_team = Team.objects.create(name=team.team_name, icpcid=guestid)
                    mog_user.profile.teams.add(mog_team)

                password = generate_secret_password(mog_user.id)
                mog_user.set_password(password)
                mog_user.save()
                self.register_team(contest, team=mog_team, site=team.group)

                mog_team.description = self.get_description_of_team(team)
                mog_team.institution = self.institutions[team.institution]
                mog_team.save()
                id += 1

        self.messages.append({'type': 'success', 'message': 'Registered %d teams in \'%s\' contest' % (id-1, contest.name)})
        return self.messages
