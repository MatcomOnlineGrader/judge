import collections
import hashlib
import os
import re
import shutil
import subprocess

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management import BaseCommand
from django.db.models import Q
import requests

from api.models import Contest, User
from collections import namedtuple

MatchedSubmission = namedtuple("MatchedSubmission", ["path", "coverage", "uid", "sid"])


MOSS_DIR_PATH = os.path.join(settings.BASE_DIR, "moss")
MOSS_EXE_PATH = os.path.join(MOSS_DIR_PATH, "moss")
MOSS_LANG_OVERRIDE = {"py": "python", "cpp": "cc"}
MOSS_MATCH_RE = r"http://moss\.stanford\.edu/results/\d+/\d+/match\d+\.html"
MOG_URL = "https://matcomgrader.com"


class Command(BaseCommand):
    """
    How to use:
        python manage.py moss --contest 6273 --users 196 --exclude-problems J --exclude-guests

    More info about MOSS:
        https://theory.stanford.edu/~aiken/moss/
    """

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument("--contest", type=int, help="Contest ID")
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
            help="User IDs that we want to include in the search anyway",
        )
        parser.add_argument(
            "--exclude-guests",
            action="store_true",
            help="If provided, we will exclude all submissions from guest teams.",
        )

    def mkdir(self, path):
        if not os.path.exists(path):
            os.mkdir(path)
        return path

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

    def upload2moss(self, contest_dir, letter, ext):
        """
        TBD
        """
        command = [
            MOSS_EXE_PATH,
            "-l",
            MOSS_LANG_OVERRIDE.get(ext, ext),
            os.path.join(contest_dir, letter, ext, "**.%s" % ext),
        ]
        output = subprocess.getoutput(" ".join(command))
        lines = list(
            filter(
                lambda line: line.startswith("http://moss.stanford.edu"),
                output.split(),
            )
        )
        return lines[0] if lines else None

    def parse_moss_content(self, url):
        """
        Parse MOSS content into a more structured format.
        """
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        matches = {}
        for link in soup.find_all("a"):
            href = link.get("href")
            text = link.text.strip()
            if re.match(MOSS_MATCH_RE, href):
                if href not in matches:
                    matches[href] = {
                        "url": href,
                        "files": [],
                        "lines": None,
                        "pos": int(href.split("/")[-1].split(".")[0].lstrip("match")),
                    }
                path, coverage = text.split()
                user_id, submission_id = map(
                    int, os.path.split(path)[-1].split(".")[0].split("-")
                )
                matches[href]["files"].append(
                    MatchedSubmission(
                        path=path,
                        uid=user_id,
                        sid=submission_id,
                        coverage=int("".join([c for c in coverage if c.isdigit()])),
                    )
                )
        return matches

    def rank_moss_results(self, contest_dir, urls):
        """
        Given a set of MOSS results, this function parses the output of each
        page and ranks the matches with additional information.
        """
        matches = []
        for url in urls:
            matches.extend(self.parse_moss_content(url).values())

        # First, let's filter out all matches that compare two files sent by the same team.
        matches = filter(
            lambda match: len(set(map(lambda file: file.uid, match["files"]))) > 1,
            matches,
        )

        # Then, let's sort by the average coverage of all files. I'm not sure if this is the
        # best approach, but it might work.
        matches = sorted(
            matches,
            key=lambda match: (
                -1.0
                * sum(map(lambda file: file.coverage, match["files"]))
                / len(match["files"])
            ),
        )

        # Create an HTML report with a bit more of information
        soup = BeautifulSoup("<html></html>", "html.parser")

        table = soup.new_tag("table")
        header = soup.new_tag("tr")
        for name in [
            "Team 1",
            "Team 2",
            "Submission 1",
            "Submission 2",
            "Problem",
            "AVG Coverage (%)",
            "MOSS",
        ]:
            th = soup.new_tag("th")
            th.string = name
            header.append(th)
        table.append(header)

        def link(soup, value, href, bgcolor=None):
            td = soup.new_tag("td")
            a = soup.new_tag("a", href=href)
            a.string = value
            td.append(a)
            if bgcolor:
                (r, g, b) = bgcolor
                td["style"] = f"background-color: rgba({r}, {g}, {b}, 0.3);"
            return td

        def text(soup, value):
            td = soup.new_tag("td")
            td.string = value
            return td

        def hash_to_rgb(*args):
            combined = ",".join(map(str, args))
            hash_object = hashlib.sha256(combined.encode())
            hex_dig = hash_object.hexdigest()
            r = int(hex_dig[0:2], 16)  # First two hex digits for Red
            g = int(hex_dig[2:4], 16)  # Next two hex digits for Green
            b = int(hex_dig[4:6], 16)  # Next two hex digits for Blue
            return (r, g, b)

        for match in matches:
            # Gather all necessary info
            s1 = match["files"][0]
            s2 = match["files"][1]
            user_1 = User.objects.get(pk=s1.uid)
            color1 = hash_to_rgb(s1.uid)
            user_2 = User.objects.get(pk=s2.uid)
            color2 = hash_to_rgb(s2.uid)
            score = (s1.coverage + s2.coverage) / 2.0
            problem = s1.path.split("/")[-3]
            # Create the HTML row
            tr = soup.new_tag("tr")
            tr.append(
                link(soup, user_1.username, "%s/user/%d" % (MOG_URL, user_1.pk), color1)
            )
            tr.append(
                link(soup, user_2.username, "%s/user/%d" % (MOG_URL, user_2.pk), color2)
            )
            tr.append(
                link(
                    soup,
                    "%d (%d %%)" % (s1.sid, s1.coverage),
                    "%s/submission/%d" % (MOG_URL, s1.sid),
                )
            )
            tr.append(
                link(
                    soup,
                    "%d (%d %%)" % (s2.sid, s2.coverage),
                    "%s/submission/%d" % (MOG_URL, s2.sid),
                )
            )
            tr.append(text(soup, problem))
            tr.append(text(soup, "%.2lf" % score))
            tr.append(link(soup, match["url"], match["url"]))
            table.append(tr)

        soup.append(table)

        report_path = os.path.join(contest_dir, "report.html")
        with open(report_path, "w") as f:
            f.write(soup.prettify())

        print("Report stored in %s" % report_path)

    def handle(self, *args, **options):
        contest = Contest.objects.get(pk=options.get("contest"))
        contest_dir = self.create_output_folder(contest)
        exclude_guests = options.get("exclude_guests")

        print("Output dir: %s" % contest_dir)
        print("Contest   : %s" % contest.name)

        results = {}
        for problem in contest.problems.order_by("position").all():
            if problem.letter in options.get("exclude_problems"):
                continue
            results[problem.letter] = collections.defaultdict(int)
            problem_dir = self.mkdir(os.path.join(contest_dir, str(problem.letter)))
            for submission in problem.submissions.filter(
                (Q(instance__real=True) & Q(result__name__iexact="accepted"))
                | Q(user__in=(options.get("users")))
            ).all():
                if exclude_guests and "_guest_" in submission.user.username:
                    continue
                compiler = submission.compiler
                compiler_dir = self.mkdir(
                    os.path.join(problem_dir, compiler.file_extension)
                )
                submission_path = os.path.join(
                    compiler_dir,
                    "%d-%d.%s"
                    % (
                        submission.user_id,
                        submission.id,
                        submission.compiler.file_extension,
                    ),
                )
                with open(submission_path, "w") as f:
                    f.write(submission.source)
                results[problem.letter][compiler.file_extension] += 1

        urls = []
        for letter, extension_count in sorted(results.items()):
            for ext, count in sorted(extension_count.items()):
                if count >= 2:
                    url = self.upload2moss(contest_dir, letter, ext)
                    urls.append(url)
                    print(
                        ":: %s (%s) -> %s (%d files)"
                        % (letter, ext.ljust(5), url, count)
                    )

        self.rank_moss_results(contest_dir, urls)
