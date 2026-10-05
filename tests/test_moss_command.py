import os
import subprocess
import tempfile
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from api.management.commands import moss
from api.models import Compiler

from . import FixturedTestCase

RESULTS_URL = "http://moss.stanford.edu/results/1/2345678"


def moss_page(*matches, url=RESULTS_URL):
    """
    The MOSS results at `url` listing `matches`, each a (submission 1,
    coverage 1, submission 2, coverage 2, lines in common) tuple.
    """

    def file(href, submission, coverage):
        ext = submission.compiler.file_extension
        return '<TD><A HREF="%s">%s/%s/%d-%d.%s (%d%%)</A>\n' % (
            href,
            submission.problem.letter,
            ext,
            submission.user_id,
            submission.id,
            ext,
            coverage,
        )

    rows = ""
    for k, (s1, c1, s2, c2, lines) in enumerate(matches):
        href = "%s/match%d.html" % (url, k)
        rows += "<TR>%s%s<TD ALIGN=right>%d\n" % (
            file(href, s1, c1),
            file(href, s2, c2),
            lines,
        )
    return (
        "<HTML><HEAD><TITLE>Moss Results</TITLE></HEAD><BODY>Moss Results<p>"
        '[ <A HREF="http://moss.stanford.edu/general/format.html">How to Read</A> ]'
        "<TABLE><TR><TH>File 1<TH>File 2<TH>Lines Matched\n%s</TABLE></BODY></HTML>"
        % rows
    )


@override_settings(MOSS_USERID="123")
class MossCommandTestCase(FixturedTestCase):
    def setUp(self):
        super().setUp()
        self.contest = self.past_contest
        self.kotlin = Compiler.objects.create(
            language="kotlin",
            name="Kotlin 1.7.21",
            path="kotlinc",
            arguments="{0}",
            file_extension="kt",
            exec_extension="class",
        )

        self.alice = self.newUser("alice")
        self.bob = self.newUser("bob")
        self.team = self.newTeam(2, name="Ñandú")
        self.member1, self.member2 = [p.user for p in self.team.profiles.all()]
        self.instances = {
            self.alice: self.newContestInstance(self.contest, self.alice),
            self.bob: self.newContestInstance(self.contest, self.bob),
        }
        team_instance = self.newContestInstance(self.contest, None, team=self.team)
        self.instances[self.member1] = self.instances[self.member2] = team_instance

        moss_dir = tempfile.TemporaryDirectory()
        self.addCleanup(moss_dir.cleanup)
        patch = mock.patch.object(moss, "MOSS_DIR_PATH", moss_dir.name)
        patch.start()
        self.addCleanup(patch.stop)
        self.contest_dir = os.path.join(
            moss_dir.name, "moss-output-%d" % self.contest.pk
        )

        media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(media_dir.cleanup)
        media = override_settings(MEDIA_ROOT=media_dir.name)
        media.enable()
        self.addCleanup(media.disable)
        self.reports_dir = os.path.join(
            media_dir.name, "contests", str(self.contest.pk), "moss"
        )

    def submit(
        self, user, compiler, result=None, minutes=60, practice=False, problem=None
    ):
        """
        `user` submits `minutes` after their contest started. Practice submissions
        (after the contest) aren't linked to any contest instance.
        """
        submission = self.newSubmission(
            self.instances[user],
            user,
            minutes=minutes,
            problem=problem or self.problem1,
            compiler=compiler,
            source="int main() { return %d; }  // ñ\n" % user.pk,
            result=result or self.accepted,
        )
        if practice:
            submission.instance = None
            submission.save()
        return submission

    def run_moss(self, outputs, pages, *args):
        """
        Runs the command, with the MOSS client printing `outputs[language]`
        and `pages[url]` being the results at `url`.
        """
        calls = []

        def run(command, cwd, env, **kwargs):
            calls.append((command, cwd, env["MOSS_USERID"]))
            return subprocess.CompletedProcess(command, 0, outputs[command[3]])

        def get(url, **kwargs):
            return mock.Mock(content=pages[url].encode(), url=url)

        stdout, stderr = StringIO(), StringIO()
        with mock.patch.object(moss.subprocess, "run", run), mock.patch.object(
            moss.requests, "get", get
        ):
            try:
                call_command(
                    "moss",
                    "--contest",
                    self.contest.pk,
                    *args,
                    stdout=stdout,
                    stderr=stderr,
                )
            finally:
                self.stdout, self.stderr = stdout.getvalue(), stderr.getvalue()
        return calls

    def read_report(self):
        [name] = os.listdir(self.reports_dir)
        self.assertRegex(name, r"^[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}\.html$")
        self.assertIn(
            "URL: https://matcomgrader.com/media/contests/%d/moss/%s"
            % (self.contest.pk, name),
            self.stdout,
        )
        with open(os.path.join(self.reports_dir, name), encoding="utf-8") as f:
            return f.read()

    def test_ranks_matches_between_different_teams(self):
        alice = self.submit(self.alice, self.cpp)
        bob = self.submit(self.bob, self.cpp)
        member1 = self.submit(self.member1, self.cpp)
        member2 = self.submit(self.member2, self.cpp)
        self.submit(self.bob, self.cpp, result=self.wrong_answer)
        self.submit(self.alice, self.kotlin)

        calls = self.run_moss(
            {"cc": "Query submitted.\n%s\n" % RESULTS_URL},
            {
                RESULTS_URL: moss_page(
                    (alice, 50, member1, 40, 30),
                    (member1, 99, member2, 99, 40),
                    (alice, 90, bob, 80, 10),
                )
            },
        )

        [(command, cwd, userid)] = calls
        self.assertEqual(cwd, self.contest_dir)
        self.assertEqual(userid, "123")
        self.assertEqual(
            command[:8],
            ["perl", moss.MOSS_EXE_PATH, "-l", "cc", "-m", "10", "-n", "250"],
        )
        self.assertEqual(
            command[8:],
            sorted(
                "A/cpp/%d-%d.cpp" % (s.user_id, s.id)
                for s in [alice, bob, member1, member2]
            ),
        )
        self.assertIn("Skipped 1 submission(s) in Kotlin 1.7.21", self.stderr)
        self.assertIn("2 matches between different teams", self.stdout)

        report = self.read_report()
        self.assertNotIn('/submission/%d"' % member2.id, report)
        self.assertIn("Ñandú", report)
        # Most lines in common first, and those with few hidden at first
        self.assertLess(
            report.index('/submission/%d"' % member1.id),
            report.index('/submission/%d"' % bob.id),
        )
        self.assertIn('<tr class="minor" id="match-2">', report)
        self.assertIn("Show 1 more matches (fewer than 15 lines in common)", report)
        # The judge can sort matches by coverage too, with the embedded script
        self.assertIn(
            '<th class="sortable" data-order="desc">Lines in common</th>', report
        )
        self.assertIn('<th class="sortable">AVG Coverage (%)</th>', report)
        self.assertIn("const value = (row) => parseFloat(", report)
        self.assertIn("Confidential: don't share this report.", report)
        self.assertIn('<meta name="referrer" content="no-referrer">', report)
        # What it took into account
        self.assertIn("/contest/overview/%d" % self.contest.pk, report)
        self.assertIn("A (cpp): 4 submissions", report)
        self.assertIn('href="%s"' % RESULTS_URL, report)
        self.assertIn(
            "Kotlin 1.7.21: 1 submission, MOSS doesn't support the language", report
        )
        self.assertIn("2 matches between different teams", report)
        self.assertIn("Left out 1 match between submissions of the same team", report)

    def test_only_official_submissions_count(self):
        carol = self.newUser("carol")
        dave = self.newUser("dave")
        self.instances[carol] = self.newContestInstance(
            self.contest,
            carol,
            real=False,
            start_date=self.contest.end_date + timezone.timedelta(days=1),
        )
        self.instances[dave] = self.newContestInstance(self.contest, dave)
        alice = self.submit(self.alice, self.cpp)
        bob = self.submit(self.bob, self.cpp, result=self.wrong_answer)
        # After the contest (5 hours in, it lasts 4), or in a virtual one
        self.submit(self.bob, self.cpp, minutes=300, practice=True)
        self.submit(self.member1, self.cpp, minutes=300)
        self.submit(carol, self.cpp)
        self.submit(dave, self.cpp, minutes=300, practice=True)

        [(command, _, _)] = self.run_moss(
            {"cc": RESULTS_URL},
            {RESULTS_URL: moss_page()},
            "--users",
            self.bob.pk,
            dave.pk,
        )

        self.assertEqual(
            command[8:],
            sorted("A/cpp/%d-%d.cpp" % (s.user_id, s.id) for s in [alice, bob]),
        )
        self.assertIn(
            "User %d has no submissions during the contest." % dave.pk, self.stderr
        )
        report = self.read_report()
        self.assertIn("/user/%d" % self.bob.pk, report)
        self.assertIn("(none)", report)

    def test_pairs_matching_on_more_problems_come_first(self):
        problem2 = self.newProblem("B", self.contest, 2)
        alice = self.submit(self.alice, self.cpp)
        bob = self.submit(self.bob, self.cpp)
        member1 = self.submit(self.member1, self.cpp)
        alice2 = self.submit(self.alice, self.py2, problem=problem2)
        bob2 = self.submit(self.bob, self.py2, problem=problem2)
        python_url = RESULTS_URL + "0"

        self.run_moss(
            {"cc": RESULTS_URL, "python": python_url},
            {
                RESULTS_URL: moss_page(
                    (alice, 60, member1, 60, 40), (alice, 30, bob, 30, 8)
                ),
                python_url: moss_page((alice2, 40, bob2, 40, 9), url=python_url),
            },
        )

        report = self.read_report()
        self.assertIn(
            "2 pairs with similar code, 1 of them on more than one problem", report
        )
        # alice and bob match on two problems, if only on a few lines each time
        self.assertLess(report.index("B: 9 lines"), report.index("A: 40 lines"))
        self.assertIn('<a href="#match-2">B: 9 lines</a>', report)
        self.assertNotIn('id="all-pairs"', report)
        self.assertIn("Show 2 more matches (fewer than 15 lines in common)", report)

    def test_complains_when_moss_gives_no_results(self):
        self.submit(self.alice, self.cpp)
        self.submit(self.bob, self.cpp)
        self.submit(self.alice, self.py2)
        self.submit(self.bob, self.py2)

        with self.assertRaisesMessage(
            CommandError, "MOSS failed for 1 of 2 groups: A (py)."
        ):
            self.run_moss(
                {
                    "cc": "%s\n" % RESULTS_URL,
                    "python": "Query submitted.\nError: No files uploaded to compare.\n",
                },
                {RESULTS_URL: moss_page()},
            )
        self.assertIn("Error: No files uploaded to compare.", self.stderr)
        self.assertIn("0 matches between different teams", self.stdout)
        self.assertIn(
            "A (py): 2 submissions, MOSS failed: no results URL from MOSS (exit code 0):"
            " Error: No files uploaded to compare.",
            self.read_report(),
        )

    def test_complains_about_unexpected_results(self):
        self.submit(self.alice, self.cpp)
        self.submit(self.bob, self.cpp)
        page = moss_page().replace(
            "</TABLE>",
            '<TR><TD><A HREF="%s/match0.html">alice.cpp (50%%)</A>'
            '<TD><A HREF="%s/match0.html">bob.cpp (50%%)</A><TD>10</TABLE>'
            % (RESULTS_URL, RESULTS_URL),
        )

        with self.assertRaisesMessage(CommandError, "No report was written."):
            self.run_moss({"cc": RESULTS_URL}, {RESULTS_URL: page})
        self.assertIn("unexpected file 'alice.cpp (50%)'", self.stderr)
        self.assertFalse(os.path.exists(self.reports_dir))

    def test_validates_arguments(self):
        with self.assertRaisesMessage(CommandError, "Contest 0 does not exist."):
            call_command("moss", "--contest", 0)
        with self.assertRaisesMessage(CommandError, "has no problem B."):
            call_command(
                "moss", "--contest", self.contest.pk, "--exclude-problems", "b"
            )
        with self.assertRaisesMessage(CommandError, "no users with ID 0."):
            call_command("moss", "--contest", self.contest.pk, "--users", 0)
        with override_settings(MOSS_USERID=""):
            with self.assertRaisesMessage(CommandError, "Set MOSS_USERID"):
                call_command("moss", "--contest", self.contest.pk)
        with mock.patch.object(moss.shutil, "which", return_value=None):
            with self.assertRaisesMessage(CommandError, "needs perl"):
                call_command("moss", "--contest", self.contest.pk)
