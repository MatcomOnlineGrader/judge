from io import TextIOWrapper

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from api.models import (
    Contest,
    ContestInstance,
    Institution,
    Team,
    User,
)

from mog.baylor.utils import generate_secret_password, generate_username


class BaylorTeam:
    def __init__(self):
        self.coach_id = ""
        self.members_id = []
        self.id = ""
        self.institution_id = ""
        self.institution_name = ""
        self.institution_short_name = ""
        self.country = ""
        self.site_id = ""
        self.name = ""
        self.status = ""


class BaylorInstitution:
    def __init__(self):
        self.name = ""
        self.short_name = ""
        self.country = ""


class ProcessImportBaylor:
    """
    This class reads and process a .tab file with the institutions' information from Baylor and updates/creates
    the corresponding institutions in th DB.

    zip_ref: Zip file reference that contains the .tab files
    contest_id: Contest where the teams should be registered
    prefix: Prefix to add to each team's account
    select_pending_teams: Whether create or not pending teams (default: False)
    """

    def __init__(self, zip_ref, contest_id, prefix, select_pending_teams=False):
        self.institutions = {}
        self.baylor_institutions = {}
        self.persons = {}
        self.teams = {}
        self.groups = {}
        self.prefix = prefix
        self.contest_id = contest_id
        self.select_pending_teams = select_pending_teams

        self.zip_ref = zip_ref
        self.school_file = None
        self.site_file = None
        self.person_file = None
        self.team_file = None
        self.team_person_file = None

        self.messages = []

    def import_institutions(self):
        with TextIOWrapper(
            self.zip_ref.open(self.school_file, "r"), encoding="utf-8"
        ) as f:
            lines = list(f.readlines())
            country_names = {
                "PRI": "Puerto Rico",
                "TTO": "Trinidad & Tobago",
                "ATG": "Antigua & Barbuda",
                "JAM": "Jamaica",
                "DOM": "Dominican Republic",
                "CUB": "Cuba",
            }
            count = 0

            for line in lines[1:]:
                fields = line.split("\t")
                icpcid = fields[0]
                name = fields[2]
                short_name = fields[3]
                country = fields[5]

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

                if country not in country_names:
                    self.messages.append(
                        {
                            "type": "warning",
                            "message": "WARNING: Country %s was not found" % country,
                        }
                    )

                self.institutions[icpcid] = institution
                baylor_institution = BaylorInstitution()
                baylor_institution.name = name
                baylor_institution.short_name = short_name
                baylor_institution.country = country_names[country]
                self.baylor_institutions[icpcid] = baylor_institution

            self.messages.append(
                {"type": "success", "message": "Loaded %d institutions" % count}
            )

    def import_sites(self):
        with TextIOWrapper(
            self.zip_ref.open(self.site_file, "r"), encoding="utf-8"
        ) as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split("\t")
                id = fields[0]
                name = fields[1]
                self.groups[id] = name
                count += 1
            self.messages.append(
                {"type": "success", "message": "%d sites imported" % count}
            )

    def import_persons(self):
        with TextIOWrapper(
            self.zip_ref.open(self.person_file, "r"), encoding="utf-8"
        ) as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split("\t")
                id = fields[0]
                name = fields[4]
                count += 1
                self.persons[id] = name
            self.messages.append(
                {"type": "success", "message": "%d persons imported" % count}
            )

    def import_teams(self):
        with TextIOWrapper(
            self.zip_ref.open(self.team_file, "r"), encoding="utf-8"
        ) as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split("\t")
                status = fields[5]
                if not self.select_pending_teams and status != "A":
                    continue

                institution_id = fields[2]
                team = BaylorTeam()
                team.id = fields[0]
                team.name = fields[1]
                team.institution_id = institution_id
                team.site_id = fields[3]
                team.status = "pending" if status != "A" else "accepted"
                team.country = self.baylor_institutions[institution_id].country
                team.institution_name = self.baylor_institutions[institution_id].name
                team.institution_short_name = self.baylor_institutions[
                    institution_id
                ].short_name

                self.teams[team.id] = team
                count += 1
            self.messages.append(
                {"type": "success", "message": "%d teams imported" % count}
            )

    def import_team_members(self):
        with TextIOWrapper(
            self.zip_ref.open(self.team_person_file, "r"), encoding="utf-8"
        ) as f:
            lines = list(f.readlines())
            count = 0
            for line in lines[1:]:
                fields = line.split("\t")
                person_id = fields[0]
                team_id = fields[1]
                team_role = fields[3]
                if not self.teams.get(team_id):
                    continue
                if team_role == "CONTESTANT":
                    self.teams[team_id].members_id.append(person_id)
                    count += 1
                elif team_role == "COACH":
                    self.teams[team_id].coach_id = person_id
                    count += 1
            self.messages.append(
                {"type": "success", "message": "%d team members imported" % count}
            )

    def get_description_of_team(self, team):
        result = ""
        result += self.persons[team.coach_id] + "[c]" + "\n"
        for member_id in team.members_id:
            result += self.persons[member_id] + "\n"
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

        self.load_files()

        self.import_institutions()
        self.import_sites()
        self.import_persons()
        self.import_teams()
        self.import_team_members()

        def key(team):
            return team.site_id, team.institution_id, team.name

        teams = sorted(self.teams.values(), key=key)

        id = 1
        registered = 0

        with transaction.atomic():
            for team in teams:
                icpcid = team.id
                prefix_icpc = "%s_icpc_" % self.prefix
                r_username_prefix = rf"^{prefix_icpc}\d+$"

                # check if {icpcid} is already registered
                if ContestInstance.objects.filter(
                    contest_id=contest.pk, team__icpcid=icpcid
                ).exists():
                    self.messages.append(
                        {
                            "type": "warning",
                            "message": 'Team "%s" is already registered in this contest'
                            % team.name,
                        }
                    )
                    continue

                # if the prev conditional is false, then the current team has a different icpcid,
                # means that the current team is different to the one already imported
                # skiped it because two equals team name cannot coexist in the same contest
                if ContestInstance.objects.filter(
                    contest_id=contest.pk, team__name=team.name
                ).exists():
                    self.messages.append(
                        {
                            "type": "warning",
                            "message": 'There is a team registered with the same name "%s", please check it out, import skiped!'
                            % team.name,
                        }
                    )
                    continue

                # find existing team with the same {icpcid} and has an user with the same {prefix}
                mog_team = Team.objects.filter(
                    icpcid=icpcid, profiles__user__username__regex=r_username_prefix
                ).first()

                created = False
                # if mog_team exists retrieve the user from itself
                if mog_team:
                    tmp_user = mog_team.profiles.filter(
                        user__username__regex=r_username_prefix
                    ).first()
                    mog_user = tmp_user.user
                else:
                    username = generate_username(prefix_icpc, id)
                    # while username already exists, generate new one
                    # make sure the created user is brand new
                    while User.objects.filter(username=username).exists():
                        id += 1
                        username = generate_username(prefix_icpc, id)

                    mog_user = self.create_user(
                        username, "", self.institutions[team.institution_id]
                    )
                    mog_team = Team.objects.create(name=team.name, icpcid=icpcid)
                    mog_user.profile.teams.add(mog_team)
                    created = True

                password = generate_secret_password(mog_user.id)
                mog_user.set_password(password)
                mog_user.save()

                mog_team.description = self.get_description_of_team(team)
                mog_team.institution = self.institutions[team.institution_id]
                mog_team.save()

                # check if the team is not subscribe it in this contest yet
                if (
                    created
                    or not ContestInstance.objects.filter(
                        contest_id=contest.pk, team_id=mog_team.pk
                    ).exists()
                ):
                    self.register_team(
                        contest, team=mog_team, site=self.groups[team.site_id]
                    )
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

    def load_files(self):
        for infofile in self.zip_ref.infolist():
            if infofile.filename == "School.tab":
                self.school_file = infofile
            elif infofile.filename == "Site.tab":
                self.site_file = infofile
            elif infofile.filename == "Person.tab":
                self.person_file = infofile
            elif infofile.filename == "Team.tab":
                self.team_file = infofile
            elif infofile.filename == "TeamPerson.tab":
                self.team_person_file = infofile
        if (
            not self.school_file
            or not self.site_file
            or not self.person_file
            or not self.team_file
            or not self.team_person_file
        ):
            raise Exception("Some files are missing from the loaded file.")
