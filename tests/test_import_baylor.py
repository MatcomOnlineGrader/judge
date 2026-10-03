import io
import zipfile

from django.contrib.auth import authenticate

from api.models import Team
from mog.baylor.import_baylor import ProcessImportBaylor
from mog.baylor.utils import generate_secret_password
from tests import FixturedTestCase


def tab(header, rows):
    return "\n".join(["\t".join(header)] + ["\t".join(row) for row in rows]) + "\n"


def baylor_zip(teams):
    """A Baylor export with `teams` accepted teams, two contestants each."""
    persons, team_rows, team_persons = [], [], []
    for k in range(teams):
        team_rows.append([str(k), "Team %d" % k, "1", "10", "", "A", ""])
        for role in ["COACH", "CONTESTANT", "CONTESTANT"]:
            person = str(len(persons))
            persons.append([person, "", "", "", "Person %s" % person, ""])
            team_persons.append([person, str(k), "", role, ""])
    files = {
        "School.tab": tab(
            ["id", "", "name", "short", "", "country", ""],
            [["1", "", "Universidad", "UH", "", "CUB", ""]],
        ),
        "Site.tab": tab(["id", "name", ""], [["10", "Havana", ""]]),
        "Person.tab": tab(["id", "", "", "", "name", ""], persons),
        "Team.tab": tab(["id", "name", "school", "site", "", "status", ""], team_rows),
        "TeamPerson.tab": tab(["person", "team", "", "role", ""], team_persons),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_ref:
        for name, content in files.items():
            zip_ref.writestr(name, content)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


class ImportBaylorTestCase(FixturedTestCase):
    def import_baylor(self, contest, teams):
        ProcessImportBaylor(baylor_zip(teams), contest.pk, "test").handle()

    def assert_team_passwords_work(self, teams):
        for k in range(teams):
            user = Team.objects.get(icpcid=str(k)).profiles.get().user
            password = generate_secret_password(user.id)
            self.assertEqual(
                authenticate(username=user.username, password=password), user
            )

    def test_imported_teams_log_in_with_generated_password(self):
        contest = self.newContest()
        self.import_baylor(contest, teams=12)
        self.assertEqual(contest.instances.count(), 12)
        self.assert_team_passwords_work(teams=12)

    def test_reimported_teams_keep_logging_in(self):
        # The second contest reuses the users from the first one, plus a new team
        self.import_baylor(self.newContest(name="First", code="FIRST"), teams=3)
        contest = self.newContest(name="Second", code="SECOND")
        self.import_baylor(contest, teams=4)
        self.assertEqual(contest.instances.count(), 4)
        self.assert_team_passwords_work(teams=4)
