import io
import zipfile

from mog.baylor.utils import generate_secret_password


class PInstance:
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
        
        instances = self.contest.instances.select_related('team__institution__country', 'user__profile__institution__country').all()
        
        for instance in instances:
            if instance.group is None or instance.team is None or instance.team.name is None or instance.institution is None or instance.user_id is None or instance.user is None or instance.user.username is None:
                continue
            p_instance = PInstance()
            p_instance.user = instance.user.username
            p_instance.password = generate_secret_password(instance.user_id)
            p_instance.team = instance.team.name
            p_instance.institution = instance.institution.name if instance.institution.name is not None else ''
            p_instance.group = instance.group
            p_instance.country = instance.institution.country if instance.institution.country is not None else ''
            self.teams.append(p_instance)
        
        site_group = { i.group for i in self.teams }
        for site in site_group:
            self.groups[site] = []

        # sort used to generate (for every site) a file that contains all info sorted by institutions
        teams = sorted(self.teams, key = lambda x: (x.institution, x.user))

        for team in teams:
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

            for team in teams:

                if team.institution != current_institution:
                    if institution_password_output:
                        institution_password_output = institution_password_output + str('\n')
                        # append institution_password_output to site_password_output
                        site_password_output = site_password_output + institution_password_output
                        self.institution_password_output[current_institution] = institution_password_output
                        # clear institution_password_output
                        institution_password_output = ''

                    current_institution = team.institution

                    institution_password_output = institution_password_output + str(current_institution) + str('\n') + \
                        str('-' * 100) + str('\n')

                institution_password_output = institution_password_output + \
                    str('user: %s  ||  password: %s  ||  team: %s  ||  institution: %s\n' % \
                        (team.user, team.password, team.team, team.institution))
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

        # sort for generate one file sorted by user that contains all information
        teams = sorted(self.teams, key = lambda x: x.user)

        for team in teams:
            not_formated_password_output = not_formated_password_output + str('%s||%s||%s||%s||%s||%s\n' % \
                (team.user, team.password, team.team, team.country, team.institution, team.group))
            
        self.not_formated_password_output = not_formated_password_output
