"""The grader's wall-clock limit must stay looser than its CPU limit; see
CLOCK_LIMIT_MULTIPLIER in api/management/commands/grader.py."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from api.management.commands.grader import (
    CLOCK_LIMIT_EXTRA_SECONDS,
    CLOCK_LIMIT_MULTIPLIER,
    get_clock_limit,
    get_cmd_for_language_safeexec,
)


def _flag(cmd, name):
    """Value passed to `--name` in a safeexec command line, as an int."""
    parts = cmd.split()
    return int(parts[parts.index("--%s" % name) + 1])


class GetClockLimitTestCase(SimpleTestCase):
    def test_is_strictly_looser_than_the_cpu_limit(self):
        for time_limit in range(1, 21):
            self.assertGreater(get_clock_limit(time_limit), time_limit)

    def test_formula(self):
        self.assertEqual(
            get_clock_limit(3), 3 * CLOCK_LIMIT_MULTIPLIER + CLOCK_LIMIT_EXTRA_SECONDS
        )

    def test_accepts_a_string_time_limit(self):
        # multiple_limits is free-form JSON, so "Time" can arrive as a string.
        self.assertEqual(get_clock_limit("2"), get_clock_limit(2))

    def test_small_limits_get_an_absolute_margin(self):
        # A 1s limit is the common case and the one most easily tipped over by
        # host jitter, so it must gain seconds of slack, not milliseconds.
        self.assertGreaterEqual(get_clock_limit(1), 1 + CLOCK_LIMIT_EXTRA_SECONDS)


class SafeexecCommandTestCase(SimpleTestCase):
    # Every language the grader dispatches on, including the `else` fallback
    # used for compiled binaries.
    LANGUAGES = [
        "java",
        "kotlin",
        "csharp",
        "python",
        "python2",
        "python3",
        "javascript",
        "cpp",
    ]

    def _cmd(self, lang, time_limit=1, memory_limit=64):
        submission = SimpleNamespace(id=42)
        compiler = SimpleNamespace(
            path="/usr/bin/python3",
            arguments="{0}",
            file_extension="py",
            exec_extension="exe",
        )
        return get_cmd_for_language_safeexec(
            submission, compiler, lang, time_limit, memory_limit
        )

    def test_every_language_has_both_limits(self):
        # java/kotlin/csharp previously passed no --clock and relied on
        # safeexec's built-in 10s default. Every language now gets an explicit
        # wall clock derived from its own time limit.
        for lang in self.LANGUAGES:
            with self.subTest(lang=lang):
                cmd = self._cmd(lang)
                self.assertIn("--cpu ", cmd)
                self.assertIn("--clock ", cmd)

    def test_clock_limit_is_strictly_looser_than_cpu_limit(self):
        for lang in self.LANGUAGES:
            for time_limit in (1, 2, 5, 10):
                with self.subTest(lang=lang, time_limit=time_limit):
                    cmd = self._cmd(lang, time_limit=time_limit)
                    self.assertEqual(_flag(cmd, "cpu"), time_limit)
                    self.assertEqual(_flag(cmd, "clock"), get_clock_limit(time_limit))
                    self.assertGreater(_flag(cmd, "clock"), _flag(cmd, "cpu"))


class ParseUidsTestCase(SimpleTestCase):
    def test_range(self):
        from api.management.commands.grader import parse_uids

        self.assertEqual(parse_uids("10000-19999"), (10000, 19999))
        self.assertEqual(parse_uids("20000-20000"), (20000, 20000))

    def test_unset_means_safeexec_default(self):
        from api.management.commands.grader import parse_uids

        self.assertIsNone(parse_uids(None))
        self.assertIsNone(parse_uids(""))

    def test_rejects_what_safeexec_would_reject(self):
        from api.management.commands.grader import parse_uids

        for bad in ("10000", "a-b", "19999-10000", "100-200", "60000-70000", "1-2-3"):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    parse_uids(bad)


class SafeexecUidsTestCase(SafeexecCommandTestCase):
    def test_every_language_passes_the_range(self):
        for lang in self.LANGUAGES:
            with self.subTest(lang=lang):
                cmd = get_cmd_for_language_safeexec(
                    SimpleNamespace(id=42),
                    SimpleNamespace(
                        path="/usr/bin/python3",
                        arguments="{0}",
                        file_extension="py",
                        exec_extension="exe",
                    ),
                    lang,
                    1,
                    64,
                    (10000, 19999),
                )
                self.assertTrue(cmd.startswith("safeexec --uids 10000 19999 "))

    def test_no_range_leaves_the_command_as_before(self):
        for lang in self.LANGUAGES:
            with self.subTest(lang=lang):
                self.assertNotIn("--uids", self._cmd(lang))
