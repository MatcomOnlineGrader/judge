import csv

from django.db import transaction

from api.models import (
    Institution,
    Contest,
    Team,
    User,
    ContestInstance
)

from mog.baylor.utils import generate_secret_password


class TeamData:
    def __init__(self):
        self.institution = ''
        self.team = ''
        self.coach = ''
        self.contestant1 = ''
        self.contestant2 = ''
        self.contestant3 = ''


class MappedColums:
    def __init__(self):
        self.institution = 0
        self.team = 0
        self.coach = 0
        self.contestant1 = 0
        self.contestant2 = 0
        self.contestant3 = 0


class ProcessImportTeam:
    """
    This class reads and process the csv file. On every row its suppose to be a team with all information like:
    institution: Institución representada
    team: Nombre del equipo
    coach: Nombre coach/representante
    contestant1: C1- Nombre completo
    contestant2: C2- Nombre completo
    contestant3: C3- Nombre completo
    
    csv_ref: Csv file reference that contains the team information
    contest_id: Contest where the teams should be registered
    prefix: Prefix to add to each team's account
    group: Name of the group of teams
    """
    def __init__(self, csv_ref, contest_id, prefix, group):
        self.institutions = {}
        self.teams = []
        self.prefix = prefix
        self.contest_id = contest_id
        
        self.csv_ref = csv_ref
        self.group = group
        self.csv_mapped = None
        self.mapped_columns = MappedColums()

        self.messages = []


    def import_institutions(self):
        count = 0
        for line in self.csv_mapped[1:]:
            inst = line[self.mapped_columns.institution]
            name = inst.split(" (")[0]
            institution = Institution.objects.filter(name=name).first()
            if institution is None:
                self.messages.append({'type': 'warning', 'message': 'WARNING: Institutions %s was not found' % name })
            self.institutions[name] = institution
            count += 1
        self.messages.append({'type': 'success', 'message': 'Loaded %d institutions' % count })

    def import_team_members(self):
        count = 0
        for line in self.csv_mapped[1:]:
            team = TeamData()
            team.team = line[self.mapped_columns.team]
            inst = line[self.mapped_columns.institution]
            team.institution = inst.split(" (")[0]
            team.coach = line[self.mapped_columns.coach]
            team.contestant1 = line[self.mapped_columns.contestant1]
            team.contestant2 = line[self.mapped_columns.contestant2]
            team.contestant3 = line[self.mapped_columns.contestant3]
            self.teams.append(team)
            count += 1
        self.messages.append({'type': 'success', 'message': 'Loaded %d teams' % count })


    def get_description_of_team(self, team):
        result = ''
        if team.coach is not None:
            result += team.coach + '[c]' + '\n'
        if team.contestant1 is not None:
            result += team.contestant1 + '\n'
        if team.contestant2 is not None:
            result += team.contestant2 + '\n'
        if team.contestant3 is not None:
            result += team.contestant3 + '\n'
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


    def mapping_columns(self):
        ind = 0
        for i in self.csv_mapped[0]:
            if i == 'Institución representada': self.mapped_columns.institution = ind
            elif i == 'Nombre del equipo': self.mapped_columns.team = ind
            elif i == 'Nombre coach/representante': self.mapped_columns.coach = ind
            elif i == 'C1- Nombre completo': self.mapped_columns.contestant1 = ind
            elif i == 'C2- Nombre completo': self.mapped_columns.contestant2 = ind
            elif i == 'C3- Nombre completo': self.mapped_columns.contestant3 = ind
            ind = ind + 1


    def handle(self):
        contest = Contest.objects.get(pk=self.contest_id)
        if not contest:
            raise Exception('The contest does not exist')

        self.csv_mapped = list(csv.reader(self.csv_ref))
        self.mapping_columns()
        self.import_institutions()
        self.import_team_members()

        teams = sorted(self.teams, key=lambda x: (x.institution, x.team))

        id = 1

        with transaction.atomic():
            for team in teams:
                team_id = '%s%03d' % (self.prefix, id)
                password = ''
                mog_user = self.create_user(team_id, password, self.institutions[team.institution])
                mog_team = Team.objects.create(name=team.team)
                mog_user.profile.teams.add(mog_team)

                password = generate_secret_password(mog_user.id)
                mog_user.set_password(password)
                mog_user.save()
                self.register_team(contest, team=mog_team, user=mog_user, site=self.group)

                mog_team.description = self.get_description_of_team(team)
                mog_team.institution = self.institutions[team.institution]
                mog_team.save()
                id += 1

        self.messages.append({'type': 'success', 'message': 'Registered %d teams in \'%s\' contest' % (id-1, contest.name)})
        return self.messages
