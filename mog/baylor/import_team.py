import csv

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from api.models import Institution, Contest, Team, User, ContestInstance

from mog.baylor.utils import (
    generate_secret_password,
    hash_string,
    generate_username,
    ICPCID_GUEST_PREFIX,
    CSV_GUEST_HEADER,
)


class TeamData:
    def __init__(self):
        self.team_name = ""
        self.institution = ""
        self.coach = ""
        self.participant1 = ""
        self.participant2 = ""
        self.participant3 = ""
        self.group = ""
        self.hash = ""


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
                self.messages.append(
                    {
                        "type": "warning",
                        "message": _(
                            "WARNING: Institution <b>%s</b> was not found" % name
                        ),
                    }
                )
            else:
                count += 1
            self.institutions[name] = institution
        self.messages.append(
            {"type": "success", "message": "Loaded %d institutions" % count}
        )

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
            team.hash = hash_string(",".join(line))
            self.teams.append(team)
            count += 1
        self.messages.append({"type": "success", "message": "Loaded %d teams" % count})

    def get_description_of_team(self, team: TeamData):
        result = ""
        if team.coach:
            result += team.coach + "[c]" + "\n"
        if team.participant1:
            result += team.participant1 + "\n"
        if team.participant2:
            result += team.participant2 + "\n"
        if team.participant3:
            result += team.participant3 + "\n"
        return result

    def create_user(self, username, password, institution):
        default = {"username": username, "email": username + "@mog.com"}
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
            render_team_description_only=True,
        )

    def handle(self):
        contest = Contest.objects.get(pk=self.contest_id)
        if not contest:
            raise Exception("The contest does not exist")

        self.csv_mapped = list(csv.reader(self.csv_ref))

        if ",".join(self.csv_mapped[0]).strip() != CSV_GUEST_HEADER:
            raise Exception("CSV file header must be %s" % CSV_GUEST_HEADER)

        self.import_institutions()
        self.import_team_members()

        teams = sorted(self.teams, key=lambda x: (x.group, x.institution, x.team_name))

        id = 1
        registered = 0

        with transaction.atomic():
            for team in teams:
                guestid = "%s%s" % (ICPCID_GUEST_PREFIX, team.hash)
                prefix_guest = "%s_guest_" % self.prefix
                r_username_prefix = rf"^{prefix_guest}\d+$"

                # check if {icpcid=guestid} is already registered
                if ContestInstance.objects.filter(
                    contest_id=contest.pk, team__icpcid=guestid
                ).exists():
                    self.messages.append(
                        {
                            "type": "warning",
                            "message": 'Team "%s" is already registered in this contest'
                            % team.team_name,
                        }
                    )
                    continue

                # if the prev conditional is false, then the current team has a different icpcid,
                # means that the current team is different to the one already imported
                # skiped it because two equals team name cannot coexist in the same contest
                if ContestInstance.objects.filter(
                    contest_id=contest.pk, team__name=team.team_name
                ).exists():
                    self.messages.append(
                        {
                            "type": "warning",
                            "message": 'There is a team registered with the same name "%s", please check it out, import skiped!'
                            % team.team_name,
                        }
                    )
                    continue

                # find existing team with the same {icpcid} and has an user with the same {prefix}
                mog_team = Team.objects.filter(
                    icpcid=guestid, profiles__user__username__regex=r_username_prefix
                ).first()

                created = False
                # if mog_team exists retrieve the user from itself
                if mog_team:
                    tmp_user = mog_team.profiles.filter(
                        user__username__regex=r_username_prefix
                    ).first()
                    mog_user = tmp_user.user
                else:
                    username = generate_username(prefix_guest, id)
                    # while username already exists, generate new one
                    # make sure the created user is brand new
                    while User.objects.filter(username=username).exists():
                        id += 1
                        username = generate_username(prefix_guest, id)

                    mog_user = self.create_user(
                        username, "", self.institutions[team.institution]
                    )
                    mog_team = Team.objects.create(name=team.team_name, icpcid=guestid)
                    mog_user.profile.teams.add(mog_team)
                    created = True

                password = generate_secret_password(mog_user.id)
                mog_user.set_password(password)
                mog_user.save()

                mog_team.description = self.get_description_of_team(team)
                mog_team.institution = self.institutions[team.institution]
                mog_team.save()

                # check if the team is not subscribe it in this contest yet
                if (
                    created
                    or not ContestInstance.objects.filter(
                        contest_id=contest.pk, team_id=mog_team.pk
                    ).exists()
                ):
                    self.register_team(contest, team=mog_team, site=team.group)
                    registered += 1
                else:
                    self.messages.append(
                        {
                            "type": "warning",
                            "message": 'Team "%s" is already registered in this contest'
                            % mog_team.name,
                        }
                    )

                id += 1

        self.messages.append(
            {
                "type": "success",
                "message": "Registered %d teams in '%s' contest"
                % (registered, contest.name),
            }
        )
        return self.messages
