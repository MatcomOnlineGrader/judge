"""
Rejudge a set of submissions and compare the verdicts before and after.

Submissions are picked with filters; each one narrows the set further:

```bash
python manage.py rejudge_compare --filter-ids 101 102 150-160
python manage.py rejudge_compare --filter-contest 12 --filter-status TLE
python manage.py rejudge_compare --filter-contest 12 --filter-ids 5000-6000 \
    --filter-status TLE --filter-status MLE
```

- --filter-ids / --filter-ids-file: ids or inclusive ranges.
- --filter-contest: contest id; repeat to allow several.
- --filter-status: current verdict, as a full name or the site's abbreviation
  (AC, WA, TLE, MLE, RTE, CTE, IE, ILE); repeat to allow several.

At least one filter is required.

Steps:

1. Print a table of the matching submissions, marking which ones will be
   rejudged and which are skipped (and why). Given ids that don't exist or
   don't match the other filters are listed.
2. Ask for confirmation. Only `y`/`yes` proceeds; anything else aborts.
3. Mark each submission as pending, following the same rules as the rejudge
   button: the row is locked, and submissions already being graded or using an
   inactive compiler are left alone.
4. Wait for the running grader to judge them, then print the before/after
   comparison side by side.

Rejudging changes verdicts, and with them contest standings, just like the
rejudge button does. The command needs an interactive terminal and refuses
when more than --max submissions match.
"""

import os
import re
import sys
import time
from collections import Counter

from django.core.management import BaseCommand, CommandError
from django.db import OperationalError, transaction
from prettytable import PrettyTable, TableStyle

from api.models import Contest, Result, Submission

MAX_RANGE = 10000
MAX_LISTED_IDS = 30

# The abbreviations the site shows (see get_submission in
# mog/views/submission.py); accepted by --filter-status besides full names.
VERDICT_ABBREVIATIONS = {
    "AC": "Accepted",
    "WA": "Wrong Answer",
    "TLE": "Time Limit Exceeded",
    "IE": "Internal Error",
    "MLE": "Memory Limit Exceeded",
    "RTE": "Runtime Error",
    "CTE": "Compilation Error",
    "ILE": "Idleness Limit Exceeded",
}

# Result.color is a CSS color (the site renders `style="color: ..."`), so it
# can be a name or a hex/rgb() value. These are the names we may meet.
CSS_COLORS = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "red": (255, 0, 0),
    "darkred": (139, 0, 0),
    "maroon": (128, 0, 0),
    "crimson": (220, 20, 60),
    "orange": (255, 165, 0),
    "darkorange": (255, 140, 0),
    "gold": (255, 215, 0),
    "yellow": (255, 255, 0),
    "olive": (128, 128, 0),
    "green": (0, 128, 0),
    "darkgreen": (0, 100, 0),
    "lime": (0, 255, 0),
    "teal": (0, 128, 128),
    "cyan": (0, 255, 255),
    "aqua": (0, 255, 255),
    "blue": (0, 0, 255),
    "navy": (0, 0, 128),
    "purple": (128, 0, 128),
    "magenta": (255, 0, 255),
    "fuchsia": (255, 0, 255),
    "pink": (255, 192, 203),
    "brown": (165, 42, 42),
}
CUBE_LEVELS = [0, 95, 135, 175, 215, 255]  # xterm 256-color cube steps


def css_to_rgb(color):
    """Parse a CSS color name, #rgb, #rrggbb or rgb(r, g, b); None if unknown."""
    color = (color or "").strip().lower()
    if color in CSS_COLORS:
        return CSS_COLORS[color]
    match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", color)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))
    match = re.fullmatch(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,[^)]*)?\)", color)
    if match:
        return tuple(min(int(v), 255) for v in match.groups())
    return None


def rgb_to_ansi256(rgb):
    """Nearest color in the xterm 256-color palette (widely supported)."""

    def nearest(value):
        return min(range(6), key=lambda i: abs(CUBE_LEVELS[i] - value))

    r, g, b = (nearest(v) for v in rgb)
    return 16 + 36 * r + 6 * g + b


def paint(text, css_color, enabled):
    """Wrap text in the terminal color closest to the result's site color."""
    rgb = css_to_rgb(css_color) if enabled else None
    if rgb is None:
        return text
    return "\033[38;5;%dm%s\033[0m" % (rgb_to_ansi256(rgb), text)


def parse_ids(tokens):
    """Parse ids like ["1", "2,3", "10-12"] into [1, 2, 3, 10, 11, 12].

    Ranges are inclusive. Duplicates are dropped, keeping the first occurrence.
    """
    ids = []
    for token in re.split(r"[\s,]+", " ".join(tokens)):
        if not token:
            continue
        match = re.fullmatch(r"(\d+)-(\d+)", token)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            if start > end:
                raise CommandError("Invalid range %r: start is after end." % token)
            if end - start >= MAX_RANGE:
                raise CommandError(
                    "Range %r is too large (max %d ids)." % (token, MAX_RANGE)
                )
            ids.extend(range(start, end + 1))
        elif token.isdigit():
            ids.append(int(token))
        else:
            raise CommandError("Invalid submission id %r." % token)
    return list(dict.fromkeys(ids))


# Results a submission passes through while the grader works on it.
IN_PROGRESS_RESULTS = ["Pending", "Compiling", "Running"]


def wait_for_grader(ids, timeout, poll, on_progress):
    """Poll until none of `ids` is still being graded, or `timeout` seconds pass.

    `on_progress(judged)` is called at the start and whenever the number of
    judged submissions changes. Returns how many are still unjudged.
    """
    deadline = time.time() + timeout
    remaining = len(ids)
    on_progress(0)
    while remaining and time.time() < deadline:
        time.sleep(poll)
        left = Submission.objects.filter(
            id__in=ids, result__name__in=IN_PROGRESS_RESULTS
        ).count()
        if left != remaining:
            remaining = left
            on_progress(len(ids) - left)
    return remaining


def is_deadlock(error):
    """True if a database error is Postgres' "deadlock detected" (40P01)."""
    return getattr(error.__cause__, "pgcode", None) == "40P01"


def retry_on_deadlock(fn, attempts=5, delay=0.5):
    """Run fn(), running it again if Postgres aborts it with a deadlock.

    Changing a submission's result fires a database trigger that updates the
    problem's points and every user who submitted to it (db_scripts/), so it
    can deadlock with the grader saving results at the same time. Postgres
    rolls back one of the two transactions, which is then safe to run again.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except OperationalError as e:
            if not is_deadlock(e) or attempt == attempts:
                raise
            time.sleep(delay * attempt)


def resolve_statuses(values, known_names):
    """Turn --filter-status values into Result names.

    Accepts full names or the site's abbreviations, in any case, e.g.
    "tle" or "Time Limit Exceeded". Raises CommandError on unknown values.
    """
    by_lower = {name.lower(): name for name in known_names}
    resolved = []
    for value in values:
        key = value.strip()
        name = VERDICT_ABBREVIATIONS.get(key.upper(), key)
        if name.lower() not in by_lower:
            raise CommandError(
                "Unknown status %r. Use a result name (%s) or one of: %s."
                % (
                    value,
                    ", ".join(sorted(known_names)),
                    ", ".join(VERDICT_ABBREVIATIONS),
                )
            )
        resolved.append(by_lower[name.lower()])
    return list(dict.fromkeys(resolved))


def resolve_contests(ids):
    """Turn --filter-contest ids into Contest objects."""
    found = Contest.objects.in_bulk(ids)
    missing = [i for i in ids if i not in found]
    if missing:
        raise CommandError("Unknown contest id(s): %s." % ", ".join(map(str, missing)))
    return [found[i] for i in dict.fromkeys(ids)]


def list_ids(ids):
    """Comma-separated ids, shortened when there are many."""
    shown = ", ".join(map(str, ids[:MAX_LISTED_IDS]))
    if len(ids) > MAX_LISTED_IDS:
        shown += ", ... (%d more)" % (len(ids) - MAX_LISTED_IDS)
    return shown


def progress_bar(done, total, width=30):
    """E.g. `[█████████░░░░░░░░░░░░░░░░░░░░]  3/10`; the bar fills by done/total."""
    filled = width * done // total if total else width
    return "[%s%s] %*d/%d" % (
        "█" * filled,
        "░" * (width - filled),
        len(str(total)),
        done,
        total,
    )


def skip_reason(submission):
    """Why a submission cannot be rejudged now, or None. Mirrors the web view."""
    if not submission.compiler.active:
        return "inactive compiler"
    if submission.result.name in IN_PROGRESS_RESULTS:
        return "already being graded"
    return None


def fmt_time(ms):
    return "%d ms" % ms


def fmt_memory(num_bytes):
    return "%.1f MB" % (num_bytes / (1024 * 1024))


def contest_name(submission):
    contest = submission.problem.contest
    return contest.code if contest else "-"


def new_table(columns, align_right=()):
    table = PrettyTable(columns)
    table.set_style(TableStyle.SINGLE_BORDER)
    table.align = "l"
    for column in align_right:
        table.align[column] = "r"
    return table


class Command(BaseCommand):
    help = "Rejudge a list of submissions and compare verdicts before and after."

    def add_arguments(self, parser):
        parser.add_argument(
            "--filter-ids",
            nargs="+",
            action="extend",
            default=[],
            metavar="ID",
            help="Only these submission ids or inclusive ranges, e.g. 101 102 150-160.",
        )
        parser.add_argument(
            "--filter-ids-file",
            metavar="PATH",
            help="Like --filter-ids, reading ids separated by spaces, commas or newlines.",
        )
        parser.add_argument(
            "--filter-contest",
            action="append",
            type=int,
            default=[],
            metavar="CONTEST_ID",
            help="Only submissions to this contest's problems. Repeat to allow several.",
        )
        parser.add_argument(
            "--filter-status",
            action="append",
            default=[],
            metavar="STATUS",
            help=(
                "Only rejudge submissions whose current verdict is STATUS, e.g. "
                '"Time Limit Exceeded" or TLE. Repeat to allow several.'
            ),
        )
        parser.add_argument(
            "--max",
            type=int,
            default=100,
            help="Refuse when more than this many submissions match (default 100).",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=3600,
            help="Seconds to wait for the grader before giving up (default 3600).",
        )
        parser.add_argument(
            "--poll",
            type=int,
            default=5,
            help="Seconds between progress checks (default 5).",
        )

    def handle(self, *args, **options):
        # Django adds --no-color; also honour NO_COLOR and plain pipes/files.
        self.colors = (
            self.stdout.isatty()
            and not options["no_color"]
            and "NO_COLOR" not in os.environ
        )
        self.result_colors = dict(Result.objects.values_list("name", "color"))
        ids = self.read_ids(options)
        contests = resolve_contests(options["filter_contest"])
        statuses = resolve_statuses(options["filter_status"], self.result_colors)
        if ids is None and not contests and not statuses:
            raise CommandError(
                "Give at least one filter: --filter-ids, --filter-ids-file, "
                "--filter-contest or --filter-status."
            )
        self.show_filters(ids, contests, statuses)

        # Each filter narrows the set further.
        query = Submission.objects.all()
        if ids is not None:
            query = query.filter(id__in=ids)
        if contests:
            query = query.filter(problem__contest__in=contests)
        if statuses:
            query = query.filter(result__name__in=statuses)
        matched = query.count()
        if matched > options["max"]:
            raise CommandError(
                "%d submissions match (limit %d). Add filters to narrow it down, "
                "or pass --max to raise the limit." % (matched, options["max"])
            )

        to_rejudge, found = self.show_plan(query, ids)
        if not to_rejudge:
            self.stdout.write("Nothing to rejudge.")
            return
        if not self.confirm(to_rejudge, found):
            self.stdout.write("Aborted. Nothing was changed.")
            return

        before = self.mark_pending(to_rejudge, statuses)
        if not before:
            self.stdout.write("Nothing was marked for rejudge.")
            return
        self.wait(list(before), options["timeout"], options["poll"])
        self.show_comparison(before)

    def paint(self, result_name):
        return paint(result_name, self.result_colors.get(result_name), self.colors)

    def read_ids(self, options):
        """The ids from --filter-ids/--filter-ids-file, or None if not given."""
        tokens = list(options["filter_ids"])
        path = options["filter_ids_file"]
        if path:
            try:
                with open(path) as f:
                    tokens.append(f.read())
            except OSError as e:
                raise CommandError("Cannot read %s: %s" % (path, e))
        if not tokens:
            return None
        ids = parse_ids(tokens)
        if not ids:
            raise CommandError("--filter-ids was given but contains no ids.")
        return ids

    def show_filters(self, ids, contests, statuses):
        parts = []
        if ids is not None:
            parts.append("%d id(s)" % len(ids))
        if contests:
            parts.append(
                "contest " + " or ".join("%s (#%d)" % (c.code, c.id) for c in contests)
            )
        if statuses:
            parts.append(
                "currently " + " or ".join(self.paint(name) for name in statuses)
            )
        self.stdout.write("Filters: " + ", ".join(parts))

    def show_plan(self, query, ids):
        """Print what would happen; return the ids to rejudge and all found rows."""
        found = {
            s.id: s
            for s in query.select_related(
                "user", "problem__contest", "compiler", "result"
            ).order_by("id")
        }
        missing, filtered_out = [], []
        if ids is None:
            submissions = list(found.values())
        else:
            # Keep the order the ids were given in, and explain the ones left out.
            submissions = [found[i] for i in ids if i in found]
            left_out = [i for i in ids if i not in found]
            existing = set(
                Submission.objects.filter(id__in=left_out).values_list("id", flat=True)
            )
            missing = [i for i in left_out if i not in existing]
            filtered_out = [i for i in left_out if i in existing]

        table = new_table(
            [
                "ID",
                "User",
                "Contest",
                "Problem",
                "Compiler",
                "Result",
                "Time",
                "Memory",
                "Submitted",
                "Action",
            ],
            align_right=["ID", "Time", "Memory"],
        )
        to_rejudge = []
        for s in submissions:
            reason = skip_reason(s)
            if reason is None:
                to_rejudge.append(s.id)
            table.add_row(
                [
                    s.id,
                    s.user.username,
                    contest_name(s),
                    s.problem.title[:30],
                    s.compiler.name,
                    self.paint(s.result.name),
                    fmt_time(s.execution_time),
                    fmt_memory(s.memory_used),
                    s.date.strftime("%Y-%m-%d %H:%M"),
                    "rejudge" if reason is None else "SKIP: " + reason,
                ]
            )

        if submissions:
            self.stdout.write(table.get_string())
        if filtered_out:
            self.stdout.write(
                "Given ids not matching the other filters (%d): %s"
                % (len(filtered_out), list_ids(filtered_out))
            )
        if missing:
            self.stdout.write(
                "Given ids that don't exist (%d): %s"
                % (len(missing), list_ids(missing))
            )
        self.stdout.write(
            "%d matched, %d skipped, %d to rejudge."
            % (
                len(submissions),
                len(submissions) - len(to_rejudge),
                len(to_rejudge),
            )
        )
        return to_rejudge, found

    def confirm(self, to_rejudge, found):
        if not sys.stdin.isatty():
            raise CommandError("Refusing to run without an interactive terminal.")
        contests = sorted({contest_name(found[i]) for i in to_rejudge})
        self.stdout.write("")
        self.stdout.write(
            "This will rejudge %d submission(s) and may change verdicts and "
            "standings in: %s" % (len(to_rejudge), ", ".join(contests))
        )
        try:
            answer = input("Proceed? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            answer = ""
        return answer.strip().lower() in ("y", "yes")

    def mark_pending(self, to_rejudge, statuses):
        """Mark each submission pending, re-checking it under a lock since its
        state may have changed while the table was on screen. Returns the
        (result, time, memory) each one had before, by id."""
        pending = Result.objects.get(name__iexact="pending")
        before = {}
        for sid in to_rejudge:
            snapshot, reason = retry_on_deadlock(
                lambda: self.mark_one_pending(sid, pending, statuses)
            )
            if reason:
                self.stdout.write("Skipped #%d: %s since confirmation." % (sid, reason))
            else:
                before[sid] = snapshot
        if before:
            self.stdout.write(
                "Marked %d submission(s) as pending. Waiting for the grader "
                "(Ctrl-C stops waiting; the grader keeps going)..." % len(before)
            )
        return before

    def mark_one_pending(self, sid, pending, statuses):
        """Mark one submission pending in its own transaction.

        Returns ((result, time, memory) before, None), or (None, reason) if
        it can't be rejudged anymore.
        """
        with transaction.atomic():
            s = (
                Submission.objects.select_for_update(of=("self",))
                .select_related("compiler", "result")
                .filter(pk=sid)
                .first()
            )
            if s is None:
                return None, "deleted"
            reason = skip_reason(s)
            if reason is None and statuses and s.result.name not in statuses:
                reason = "no longer matches --filter-status (now %s)" % s.result.name
            if reason:
                return None, reason
            snapshot = (s.result.name, s.execution_time, s.memory_used)
            s.result = pending
            s.save(update_fields=["result"])
            return snapshot, None

    def wait(self, ids, timeout, poll):
        """Show a progress bar until the grader is done. On a terminal it is
        redrawn in place; otherwise a line is printed whenever it changes."""
        in_place = self.stdout.isatty()

        def show(judged):
            bar = progress_bar(judged, len(ids))
            if in_place:
                self.stdout.write("\r" + bar, ending="")
                self.stdout.flush()
            else:
                self.stdout.write(bar)

        try:
            wait_for_grader(ids, timeout, poll, show)
            if in_place:
                self.stdout.write("")  # end the progress line
        except KeyboardInterrupt:
            self.stdout.write("\nStopped waiting. Showing the results so far.")

    def show_comparison(self, before):
        after = {
            s.id: s
            for s in Submission.objects.filter(id__in=before).select_related(
                "user", "problem", "compiler", "result"
            )
        }
        table = new_table(
            [
                "ID",
                "User",
                "Problem",
                "Compiler",
                "Result before",
                "Result after",
                "Time before",
                "Time after",
                "Memory before",
                "Memory after",
                "Change",
            ],
            align_right=[
                "ID",
                "Time before",
                "Time after",
                "Memory before",
                "Memory after",
            ],
        )
        transitions = Counter()
        unfinished = 0
        for sid, (old_result, old_time, old_memory) in before.items():
            s = after[sid]
            if s.result.name in IN_PROGRESS_RESULTS:
                unfinished += 1
                change = "still grading"
            elif s.result.name != old_result:
                transitions[(old_result, s.result.name)] += 1
                change = "VERDICT CHANGED"
            else:
                change = "same verdict"
            table.add_row(
                [
                    sid,
                    s.user.username,
                    s.problem.title[:30],
                    s.compiler.name,
                    self.paint(old_result),
                    self.paint(s.result.name),
                    fmt_time(old_time),
                    fmt_time(s.execution_time),
                    fmt_memory(old_memory),
                    fmt_memory(s.memory_used),
                    change,
                ]
            )

        self.stdout.write("")
        self.stdout.write(table.get_string())
        changed = sum(transitions.values())
        self.stdout.write(
            "%d rejudged: %d same verdict, %d changed, %d still grading."
            % (len(before), len(before) - changed - unfinished, changed, unfinished)
        )
        for (old, new), count in sorted(transitions.items()):
            self.stdout.write(
                "  %s -> %s: %d" % (self.paint(old), self.paint(new), count)
            )
        if unfinished:
            self.stdout.write(
                "Some submissions were still grading; the grader will finish them. "
                "Check their verdicts on the site. Running this command again "
                "would rejudge them a second time."
            )
