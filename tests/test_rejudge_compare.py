import re
from types import SimpleNamespace

from django.core.management import CommandError
from django.test import SimpleTestCase

from api.management.commands.rejudge_compare import (
    css_to_rgb,
    list_ids,
    new_table,
    paint,
    parse_ids,
    progress_bar,
    resolve_statuses,
    skip_reason,
)


class ParseIdsTestCase(SimpleTestCase):
    def test_single_ids_ranges_and_separators(self):
        self.assertEqual(
            parse_ids(["1", "2,3", "10-12", "5\n6"]), [1, 2, 3, 10, 11, 12, 5, 6]
        )

    def test_duplicates_keep_first_occurrence(self):
        self.assertEqual(parse_ids(["3", "1-3", "2"]), [3, 1, 2])

    def test_empty_input(self):
        self.assertEqual(parse_ids([]), [])
        self.assertEqual(parse_ids(["  ,\n"]), [])

    def test_rejects_garbage(self):
        for bad in (["abc"], ["-5"], ["1-"], ["1.5"]):
            with self.subTest(bad=bad):
                with self.assertRaises(CommandError):
                    parse_ids(bad)

    def test_rejects_backwards_range(self):
        with self.assertRaises(CommandError):
            parse_ids(["10-1"])

    def test_rejects_huge_range(self):
        with self.assertRaises(CommandError):
            parse_ids(["1-1000000"])


def _submission(result, active=True):
    return SimpleNamespace(
        result=SimpleNamespace(name=result),
        compiler=SimpleNamespace(active=active),
    )


class SkipReasonTestCase(SimpleTestCase):
    def test_finished_submission_can_be_rejudged(self):
        for result in ("Accepted", "Time Limit Exceeded", "Internal Error"):
            with self.subTest(result=result):
                self.assertIsNone(skip_reason(_submission(result)))

    def test_skips_submissions_being_graded(self):
        for result in ("Pending", "Compiling", "Running"):
            with self.subTest(result=result):
                self.assertEqual(
                    skip_reason(_submission(result)), "already being graded"
                )

    def test_skips_inactive_compiler(self):
        self.assertEqual(
            skip_reason(_submission("Accepted", active=False)), "inactive compiler"
        )


class ColorTestCase(SimpleTestCase):
    def test_parses_css_names_hex_and_rgb(self):
        self.assertEqual(css_to_rgb("Red"), (255, 0, 0))
        self.assertEqual(css_to_rgb(" orange "), (255, 165, 0))
        self.assertEqual(css_to_rgb("#0f0"), (0, 255, 0))
        self.assertEqual(css_to_rgb("#1E90FF"), (30, 144, 255))
        self.assertEqual(css_to_rgb("rgb(10, 20, 30)"), (10, 20, 30))
        self.assertIsNone(css_to_rgb("not-a-color"))
        self.assertIsNone(css_to_rgb(""))
        self.assertIsNone(css_to_rgb(None))

    def test_paint(self):
        self.assertEqual(paint("Accepted", "green", enabled=False), "Accepted")
        self.assertEqual(paint("Accepted", "???", enabled=True), "Accepted")
        painted = paint("Accepted", "green", enabled=True)
        self.assertTrue(painted.startswith("\033[38;5;"))
        self.assertIn("Accepted", painted)
        self.assertTrue(painted.endswith("\033[0m"))

    def test_colored_cells_keep_the_table_aligned(self):
        # prettytable must measure the visible text, not the escape codes.
        table = new_table(["Result"])
        table.add_row([paint("Accepted", "green", enabled=True)])
        table.add_row(["Time Limit Exceeded"])
        widths = {
            len(re.sub(r"\033\[[0-9;]*m", "", line)) for line in str(table).splitlines()
        }
        self.assertEqual(len(widths), 1)


RESULT_NAMES = [
    "Accepted",
    "Wrong Answer",
    "Time Limit Exceeded",
    "Memory Limit Exceeded",
    "Runtime Error",
]


class ResolveStatusesTestCase(SimpleTestCase):
    def test_full_names_any_case(self):
        self.assertEqual(
            resolve_statuses([" time limit EXCEEDED "], RESULT_NAMES),
            ["Time Limit Exceeded"],
        )

    def test_site_abbreviations(self):
        self.assertEqual(
            resolve_statuses(["tle", "MLE", "RTE"], RESULT_NAMES),
            ["Time Limit Exceeded", "Memory Limit Exceeded", "Runtime Error"],
        )

    def test_repeats_are_merged(self):
        self.assertEqual(
            resolve_statuses(["TLE", "Time Limit Exceeded"], RESULT_NAMES),
            ["Time Limit Exceeded"],
        )

    def test_no_filter(self):
        self.assertEqual(resolve_statuses([], RESULT_NAMES), [])

    def test_unknown_status_is_rejected(self):
        for bad in (["Timeout"], ["ACC"], ["CTE"]):  # CTE's result isn't in this DB
            with self.subTest(bad=bad):
                with self.assertRaises(CommandError):
                    resolve_statuses(bad, RESULT_NAMES)


class ListIdsTestCase(SimpleTestCase):
    def test_short_and_long_lists(self):
        self.assertEqual(list_ids([1, 2, 3]), "1, 2, 3")
        self.assertTrue(list_ids(list(range(100))).endswith(", ... (70 more)"))


class ProgressBarTestCase(SimpleTestCase):
    def test_fills_by_percentage_and_shows_count(self):
        self.assertEqual(progress_bar(0, 4, width=8), "[░░░░░░░░] 0/4")
        self.assertEqual(progress_bar(1, 4, width=8), "[██░░░░░░] 1/4")
        self.assertEqual(progress_bar(4, 4, width=8), "[████████] 4/4")

    def test_count_is_padded_so_the_line_keeps_its_width(self):
        self.assertEqual(len(progress_bar(3, 120)), len(progress_bar(120, 120)))
        self.assertTrue(progress_bar(3, 120).endswith("  3/120"))


class RetryOnDeadlockTestCase(SimpleTestCase):
    @staticmethod
    def _db_error(pgcode):
        from django.db import OperationalError

        class DriverError(Exception):  # like psycopg2's errors, which carry pgcode
            pass

        cause = DriverError()
        cause.pgcode = pgcode
        error = OperationalError("boom")
        error.__cause__ = cause
        return error

    def test_retries_a_deadlock_then_succeeds(self):
        from api.management.commands.rejudge_compare import retry_on_deadlock

        calls = []

        def fn():
            calls.append(1)
            if len(calls) < 3:
                raise self._db_error("40P01")
            return "done"

        self.assertEqual(retry_on_deadlock(fn, delay=0), "done")
        self.assertEqual(len(calls), 3)

    def test_gives_up_after_the_last_attempt(self):
        from django.db import OperationalError

        from api.management.commands.rejudge_compare import retry_on_deadlock

        def fn():
            raise self._db_error("40P01")

        with self.assertRaises(OperationalError):
            retry_on_deadlock(fn, attempts=2, delay=0)

    def test_other_database_errors_are_not_retried(self):
        from django.db import OperationalError

        from api.management.commands.rejudge_compare import retry_on_deadlock

        calls = []

        def fn():
            calls.append(1)
            raise self._db_error("08006")  # connection failure

        with self.assertRaises(OperationalError):
            retry_on_deadlock(fn, delay=0)
        self.assertEqual(len(calls), 1)
