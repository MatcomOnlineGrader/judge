import io
import zipfile

from django.db.models.functions import Lower

from mog.utils import generate_secret_password

class Participant:
    def __init__(self):
        self.user = ''
        self.password = []
        self.team = ''
        self.institution = ''
        self.group = ''
        self.country = ''

class ZipTeamPassword:
    """
    This class generate a zip file with all team passwords of contest.
    """
    def __init__(self, contest):
        self.contest = contest
        self.contest_name = self.contest.name

        self.groups = {}
        self.teams = []
        self.not_formated_password_output = ''
        self.all_password_output = ''
        self.institution_password_output = {}
        self.site_password_output = {}

        self.get_groups()
        self.generate_passwords()
        self.generate_not_format_passwords()

    
    def get_groups(self):
        
        participants = self.contest.instances.select_related('team__institution__country', 'user__profile__institution__country').all()
        teams = []

        for p in participants:
            if p.group is None or p.team is None or p.team.name is None or p.institution is None or p.user_id is None or p.user is None or p.user.username is None:
                continue
            participant = Participant()
            participant.user = p.user.username
            participant.password = generate_secret_password(p.user_id)
            participant.team = p.team.name
            participant.institution = p.institution.name if p.institution.name is not None else ''
            participant.group = p.group
            participant.country = p.institution.country if p.institution.country is not None else ''
            teams.append(participant)
        
        site_group = { i.group for i in teams }
        for site in site_group:
            self.groups[site] = []

        self.teams = sorted(teams, key = lambda x: x.user)

        tmp = sorted(teams, key = lambda x: (x.institution, x.user))

        for team in tmp:
            self.groups[team.group].append(team)


    def generate_zip_team_password(self) -> bytes:
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w') as zipObj:
            zipObj.writestr(str('passwords_%s/allsites.txt' % self.contest_name), self.all_password_output)
            zipObj.writestr(str('passwords_%s/allteams.txt' % self.contest_name), self.not_formated_password_output)
            for site_password in self.site_password_output:
                zipObj.writestr(str('passwords_%s/sites/%s.txt' % (self.contest_name, site_password)), self.site_password_output[site_password])
            for institution_password in self.institution_password_output:
                zipObj.writestr(str('passwords_%s/institutions/%s.txt' % (self.contest_name, institution_password)), self.institution_password_output[institution_password])
        return content.getvalue()


    def generate_passwords(self):
        all_password_output = ''
        site_password_output = ''
        institution_password_output = ''
        current_institution = ''
        current_group_site = ''

        for site in self.groups.keys():
            
            if site_password_output:
                # append site_password_output to all_password_output
                all_password_output = all_password_output + site_password_output
                self.site_password_output[current_group_site] = site_password_output
                # clear site_password_output
                site_password_output = ''

            current_group_site = site

            all_password_output = all_password_output + str(current_group_site) + str('\n') + \
                str('=' * 100) + str('\n')
            teams = self.groups[site]

            for t in teams:

                if t.institution != current_institution:
                    if institution_password_output:
                        institution_password_output = institution_password_output + str('\n')
                        # append institution_password_output to site_password_output
                        site_password_output = site_password_output + institution_password_output
                        self.institution_password_output[current_institution] = institution_password_output
                        # clear institution_password_output
                        institution_password_output = ''

                    current_institution = t.institution

                    institution_password_output = institution_password_output + str(current_institution) + str('\n') + \
                        str('-' * 100) + str('\n')

                institution_password_output = institution_password_output + \
                    str('user: %s  ||  password: %s  ||  team: %s  ||  institution: %s\n' % \
                        (t.user, t.password, t.team, t.institution))
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


    def generate_not_format_passwords(self):
        not_formated_password_output = ''
        for t in self.teams:
            not_formated_password_output = not_formated_password_output + str('%s||%s||%s||%s||%s||%s\n' % \
                (t.user, t.password, t.team, t.country, t.institution, t.group))
            
        self.not_formated_password_output = not_formated_password_output