import collections
import datetime
import os
import re
import shutil
import subprocess
from urllib.parse import urljoin
import uuid

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation
import requests

from api.models import Contest, Submission, User
from collections import namedtuple

MatchedSubmission = namedtuple("MatchedSubmission", ["path", "coverage", "uid", "sid"])


MOSS_DIR_PATH = os.path.join(settings.BASE_DIR, "moss")
MOSS_EXE_PATH = os.path.join(MOSS_DIR_PATH, "moss")
# Compiler file extension -> MOSS language. MOSS doesn't support any other
# language we grade (e.g. Kotlin), so those submissions can't be checked.
MOSS_LANGUAGES = {
    "c": "c",
    "cpp": "cc",
    "cs": "csharp",
    "hs": "haskell",
    "java": "java",
    "js": "javascript",
    "pas": "pascal",
    "py": "python",
}
MOSS_RESULTS_RE = re.compile(r"https?://moss\.stanford\.edu/results/\S+")
MOSS_MATCH_RE = re.compile(r"match\d+\.html$")
# Each matched file is shown as "[PROBLEM_LETTER]/[EXT]/[USER_ID]-[SUBMISSION_ID].[EXT] (NN%)"
MOSS_FILE_RE = re.compile(
    r"(?P<path>(?:\S*/)?(?P<uid>\d+)-(?P<sid>\d+)\.\w+) \((?P<coverage>\d+)%\)"
)
# Seconds to wait for MOSS to compare one group of files, and to fetch its results.
MOSS_QUERY_TIMEOUT = 15 * 60
MOSS_FETCH_TIMEOUT = 60
# MOSS ignores code found in more than MOSS_MAX_SHARED files of a group (e.g.
# templates everybody uses), and lists at most MOSS_MAX_MATCHES matches.
MOSS_MAX_SHARED = 10
MOSS_MAX_MATCHES = 250
# MOSS deletes its results after this long
MOSS_RESULTS_LIFETIME = datetime.timedelta(days=14)
# The report hides at first the matches with fewer lines in common than this
# (usually short snippets anybody would write), and the pairs of teams with
# only such a match. The judge can show them.
REPORT_MIN_LINES = 15
MOG_URL = "https://matcomgrader.com"


class MossError(Exception):
    pass


class Command(BaseCommand):
    """
    How to use:
        python manage.py moss --contest 6273 --users 196 --exclude-problems J --exclude-guests

    More info about MOSS:
        https://theory.stanford.edu/~aiken/moss/
    """

    def add_arguments(self, parser):
        parser.add_argument("--contest", type=int, required=True, help="Contest ID")
        parser.add_argument(
            "--exclude-problems",
            nargs="+",
            type=str,
            default=[],
            help="Problems to exclude, usually when solutions look alike.",
        )
        parser.add_argument(
            "--users",
            nargs="+",
            type=int,
            default=[],
            help="User IDs whose contest submissions we want to include whatever their verdict.",
        )
        parser.add_argument(
            "--exclude-guests",
            action="store_true",
            help="If provided, we will exclude all submissions from guest teams.",
        )

    def warn(self, message):
        self.stderr.write(self.style.WARNING(message))

    def create_output_folder(self, contest):
        """
        Creates a folder to store all accepted submissions for the contest
        with the following structure:

        /moss-output-[CONTEST_ID]
            /[PROBLEM_LETTER]
                /[EXT]
                    [USER_ID]-[SUBMISSION_ID].[EXT]
                ...
            ...
        """
        path = os.path.join(MOSS_DIR_PATH, "moss-output-%d" % contest.id)
        shutil.rmtree(path, ignore_errors=True)
        os.mkdir(path)
        return path

    def upload2moss(self, contest_dir, paths, ext):
        """
        Sends the files in `paths` (relative to `contest_dir`, so that MOSS
        shows them as [PROBLEM_LETTER]/[EXT]/...) to MOSS and returns the URL
        of the results. Raises MossError if MOSS doesn't give one back.
        """
        command = [
            "perl",
            MOSS_EXE_PATH,
            "-l",
            MOSS_LANGUAGES[ext],
            "-m",
            str(MOSS_MAX_SHARED),
            "-n",
            str(MOSS_MAX_MATCHES),
        ] + paths
        try:
            process = subprocess.run(
                command,
                cwd=contest_dir,
                env=dict(os.environ, MOSS_USERID=settings.MOSS_USERID),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=MOSS_QUERY_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            raise MossError("no answer from MOSS after %d seconds" % MOSS_QUERY_TIMEOUT)
        match = MOSS_RESULTS_RE.search(process.stdout)
        if process.returncode != 0 or not match:
            # The client and the server both report problems in the last line
            # (e.g. "Error: No files uploaded to compare.").
            lines = process.stdout.strip().splitlines()
            raise MossError(
                "no results URL from MOSS (exit code %d): %s"
                % (process.returncode, lines[-1] if lines else "no output")
            )
        return match.group(0)

    def parse_moss_content(self, url):
        """
        Parses the results of a MOSS query: a table with a row per match, with
        the two files matched and how many lines they have in common.
        """
        try:
            response = requests.get(url, timeout=MOSS_FETCH_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as e:
            raise MossError("couldn't fetch %s: %s" % (url, e))
        # Not html.parser: MOSS doesn't close its table cells, and html5lib is
        # the one that closes them like browsers do.
        soup = BeautifulSoup(response.content, "html5lib")
        matches = []
        for row in soup.find_all("tr"):
            cells = row.find_all("td", recursive=False)
            if not cells:
                continue  # The header
            links = row.find_all("a", href=MOSS_MATCH_RE)
            lines = cells[-1].get_text(strip=True)
            if len(cells) != 3 or len(links) != 2 or not lines.isdigit():
                raise MossError(
                    "unexpected row %r in %s" % (row.get_text(" ", strip=True), url)
                )
            files = []
            for link in links:
                text = link.get_text(strip=True)
                file = MOSS_FILE_RE.fullmatch(text)
                if not file:
                    raise MossError("unexpected file %r in %s" % (text, url))
                files.append(
                    MatchedSubmission(
                        path=file["path"],
                        uid=int(file["uid"]),
                        sid=int(file["sid"]),
                        coverage=int(file["coverage"]),
                    )
                )
            matches.append(
                {
                    "url": urljoin(response.url, links[0]["href"]),
                    "files": files,
                    "lines": int(lines),
                }
            )
        return matches

    def rank_moss_results(self, contest, matches, summary):
        """
        Given the matches MOSS found, this function ranks them and stores an
        HTML report (api/templates/api/moss/report.html) in the contest's
        media folder:

        /contests/[CONTEST_ID]/moss/[RANDOM_UUID].html

        The report has every match, but hides at first the ones that are
        likely unimportant: the judge can show them with a click.
        """
        submissions = Submission.objects.select_related(
            "user", "instance__team"
        ).in_bulk([file.sid for match in matches for file in match["files"]])

        def same_team(s1, s2):
            # Team members share the contest instance, but each submits as themselves.
            return s1.user_id == s2.user_id or (
                s1.instance_id is not None and s1.instance_id == s2.instance_id
            )

        # First, let's filter out all matches that compare two files sent by the same team.
        found = len(matches)
        matches = [
            match
            for match in matches
            if not same_team(*(submissions[file.sid] for file in match["files"]))
        ]

        # Then, let's sort by the lines in common. Unlike the coverage, it
        # doesn't make a few common lines in two short programs look serious.
        matches.sort(
            key=lambda match: (
                -match["lines"],
                -sum(file.coverage for file in match["files"]),
            )
        )

        def team(submission):
            """The team (or user) that sent `submission`"""
            instance = submission.instance
            if instance and instance.team:
                return {"key": ("instance", instance.pk), "name": instance.team.name}
            return {
                "key": ("user", submission.user_id),
                "name": submission.user.username,
            }

        for k, match in enumerate(matches):
            match["id"] = "match-%d" % (k + 1)
            match["minor"] = match["lines"] < REPORT_MIN_LINES
            match["coverage"] = sum(file.coverage for file in match["files"]) / 2.0
            match["submissions"] = [
                {
                    "id": file.sid,
                    "coverage": file.coverage,
                    "user": submissions[file.sid].user,
                    "team": team(submissions[file.sid]),
                }
                for file in match["files"]
            ]

        # Pairs of teams with similar code, and all their matches: the more
        # problems a pair matches on, the less likely it's a coincidence.
        pairs = {}
        for match in matches:
            teams = sorted(
                (submission["team"] for submission in match["submissions"]),
                key=lambda team: team["key"],
            )
            pair = pairs.setdefault(
                (teams[0]["key"], teams[1]["key"]), {"teams": teams, "matches": []}
            )
            pair["matches"].append(match)
        pairs = list(pairs.values())
        for pair in pairs:
            pair["problems"] = len({match["problem"] for match in pair["matches"]})
            pair["lines"] = sum(match["lines"] for match in pair["matches"])
            pair["minor"] = pair["problems"] == 1 and all(
                match["minor"] for match in pair["matches"]
            )
        pairs.sort(key=lambda pair: (-pair["problems"], -pair["lines"]))

        now = timezone.now()
        context = dict(
            summary,
            contest=contest,
            contest_url=MOG_URL + reverse("mog:contest_overview", args=[contest.id]),
            mog_url=MOG_URL,
            date_format="Y-m-d H:i T",
            generated=now,
            expires=now + MOSS_RESULTS_LIFETIME,
            pairs=pairs,
            multi=sum(1 for pair in pairs if pair["problems"] > 1),
            hidden_pairs=sum(1 for pair in pairs if pair["minor"]),
            matches=matches,
            hidden_matches=sum(1 for match in matches if match["minor"]),
            same_team=found - len(matches),
            min_lines=REPORT_MIN_LINES,
            max_matches=MOSS_MAX_MATCHES,
            max_shared=MOSS_MAX_SHARED,
        )
        # Always in English: in Spanish, numbers would get a decimal comma,
        # which the sorting script doesn't understand.
        with translation.override("en"):
            html = render_to_string("api/moss/report.html", context)

        # Media is public, but nobody can list its folders: the random name
        # keeps the report private to whoever we share the link with.
        report = os.path.join(
            "contests", str(contest.id), "moss", "%s.html" % uuid.uuid4()
        )
        report_path = os.path.join(settings.MEDIA_ROOT, report)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)

        self.stdout.write(
            "Report stored in %s (%d matches between different teams)"
            % (report_path, len(matches))
        )
        self.stdout.write("URL: %s%s%s" % (MOG_URL, settings.MEDIA_URL, report))

    def handle(self, *args, **options):
        contest = Contest.objects.filter(pk=options["contest"]).first()
        if contest is None:
            raise CommandError("Contest %d does not exist." % options["contest"])

        problems = list(contest.problems.order_by("position"))
        exclude_problems = {letter.upper() for letter in options["exclude_problems"]}
        unknown = exclude_problems - {problem.letter for problem in problems}
        if unknown:
            raise CommandError(
                "Contest %d has no problem %s."
                % (contest.id, ", ".join(sorted(unknown)))
            )

        users = set(options["users"])
        unknown = users - set(
            User.objects.filter(pk__in=users).values_list("pk", flat=True)
        )
        if unknown:
            raise CommandError(
                "There are no users with ID %s." % ", ".join(map(str, sorted(unknown)))
            )

        if not settings.MOSS_USERID.isdigit():
            raise CommandError(
                "Set MOSS_USERID in the [moss] section of settings.ini to the "
                "userid in the script MOSS mailed you when you registered."
            )

        if not shutil.which("perl"):
            raise CommandError(
                "The MOSS client (%s) needs perl, which isn't installed."
                % MOSS_EXE_PATH
            )

        contest_dir = self.create_output_folder(contest)
        exclude_guests = options["exclude_guests"]

        self.stdout.write("Output dir: %s" % contest_dir)
        self.stdout.write("Contest   : %s" % contest.name)

        # Only official submissions count: sent during the contest by registered
        # teams. Virtual participants, and anyone solving the problems after the
        # contest, must not show up in the report.
        official = Q(
            instance__real=True,
            date__gte=contest.start_date,
            date__lte=contest.end_date,
        )
        absent = users - set(
            Submission.objects.filter(
                official, problem__contest=contest, user__in=users
            ).values_list("user_id", flat=True)
        )
        for user_id in sorted(absent):
            self.warn("User %d has no submissions during the contest." % user_id)

        # (letter, ext) -> paths of the files to compare, relative to contest_dir
        groups = collections.defaultdict(list)
        unsupported = collections.Counter()
        for problem in problems:
            if problem.letter in exclude_problems:
                continue
            for submission in problem.submissions.filter(
                official & (Q(result__name__iexact="accepted") | Q(user__in=users))
            ).select_related("user", "compiler"):
                if exclude_guests and "_guest_" in submission.user.username:
                    continue
                ext = submission.compiler.file_extension
                if ext not in MOSS_LANGUAGES:
                    unsupported[submission.compiler.name] += 1
                    continue
                compiler_dir = os.path.join(contest_dir, problem.letter, ext)
                os.makedirs(compiler_dir, exist_ok=True)
                filename = "%d-%d.%s" % (submission.user_id, submission.id, ext)
                with open(
                    os.path.join(compiler_dir, filename), "w", encoding="utf-8"
                ) as f:
                    f.write(submission.source)
                groups[problem.letter, ext].append(
                    os.path.join(problem.letter, ext, filename)
                )

        for compiler, count in sorted(unsupported.items()):
            self.warn(
                "Skipped %d submission(s) in %s: MOSS doesn't support that language."
                % (count, compiler)
            )

        matches = []
        compared = []  # (group, files, results URL, matches found)
        failed = []  # (group, files, error)
        single = []  # groups with a single file, nothing to compare it with
        for (letter, ext), paths in sorted(groups.items()):
            group = "%s (%s)" % (letter, ext)
            if len(paths) < 2:
                single.append(group)
                continue
            label = "%s (%s)" % (letter, ext.ljust(5))
            try:
                url = self.upload2moss(contest_dir, sorted(paths), ext)
                group_matches = self.parse_moss_content(url)
            except MossError as e:
                self.stderr.write(self.style.ERROR(":: %s failed: %s" % (label, e)))
                failed.append((group, len(paths), e))
                continue
            self.stdout.write(":: %s -> %s (%d files)" % (label, url, len(paths)))
            if len(group_matches) >= MOSS_MAX_MATCHES:
                self.warn(
                    "%s: MOSS lists at most %d matches, there may be more."
                    % (group, MOSS_MAX_MATCHES)
                )
            compared.append((group, len(paths), url, len(group_matches)))
            for match in group_matches:
                match["problem"] = letter
                matches.append(match)

        if not compared and not failed:
            self.warn(
                "Nothing to compare: no problem has two submissions in the same language."
            )
            return

        if compared:
            summary = {
                "users": User.objects.filter(pk__in=users).order_by("username"),
                "absent": absent,
                "exclude_guests": exclude_guests,
                "exclude_problems": sorted(exclude_problems),
                "compared": compared,
                "failed": failed,
                "single": single,
                "unsupported": sorted(unsupported.items()),
            }
            self.rank_moss_results(contest, matches, summary)

        if failed:
            message = "MOSS failed for %d of %d groups: %s." % (
                len(failed),
                len(failed) + len(compared),
                ", ".join(group for group, _, _ in failed),
            )
            if compared:
                raise CommandError(message + " The report doesn't include them.")
            raise CommandError(message + " No report was written.")
