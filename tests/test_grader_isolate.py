"""`grader --isolate` runs safeexec inside isolate; see ISOLATE in
api/management/commands/grader.py."""

import os
import shlex
import tempfile
from types import SimpleNamespace

from django.conf import settings
from django.test import SimpleTestCase

from api.management.commands.grader import (
    ISOLATE_BOXES,
    ISOLATE_FIRST_UID,
    get_box_verdict,
    get_clock_limit,
    get_cmd_for_language_isolate,
    get_cmd_for_language_safeexec,
    parse_box_id,
    read_isolate_meta,
)


def _flag(cmd, name):
    """Value of `--name=value` in an isolate command line."""
    prefix = "--%s=" % name
    return next(p[len(prefix) :] for p in shlex.split(cmd) if p.startswith(prefix))


class GetBoxVerdictTestCase(SimpleTestCase):
    def _verdict(self, meta):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(meta)
        self.addCleanup(os.remove, f.name)
        return get_box_verdict(read_isolate_meta(f.name))

    def test_safeexec_finished(self):
        # Whatever the submission did, safeexec's report stands.
        self.assertIsNone(self._verdict("time:0.021\ncg-mem:360\nexitcode:0\n"))

    def test_box_memory_kill_while_safeexec_finished(self):
        # safeexec reports the kill as a time limit (or, for Kotlin's
        # launcher script, a runtime error) and exits 0.
        self.assertEqual(
            self._verdict("time:1.2\ncg-mem:327680\ncg-oom-killed:1\nexitcode:0\n"),
            "MEMORY_LIMIT_EXCEEDED",
        )

    def test_box_stopped_safeexec(self):
        cases = [
            ("status:TO\nmessage:Time limit exceeded\n", "TIME_LIMIT_EXCEEDED"),
            ("status:SG\nexitsig:9\ncg-oom-killed:1\n", "MEMORY_LIMIT_EXCEEDED"),
            ("status:SG\nexitsig:9\n", "RUNTIME_ERROR"),
            ("status:RE\nexitcode:1\n", "INTERNAL_ERROR"),  # safeexec failed
            ("status:XX\nmessage:Cannot run proxy\n", "INTERNAL_ERROR"),
        ]
        for meta, verdict in cases:
            with self.subTest(verdict=verdict):
                self.assertEqual(self._verdict(meta), verdict)

    def test_missing_report_is_an_internal_error(self):
        # isolate failed before writing its report.
        meta = read_isolate_meta("/nonexistent/meta")
        self.assertEqual(get_box_verdict(meta), "INTERNAL_ERROR")


class IsolateConfigTestCase(SimpleTestCase):
    def test_grader_matches_isolate_cf(self):
        path = os.path.join(settings.BASE_DIR, "docker", "isolate", "isolate.cf")
        with open(path) as f:
            config = dict(
                (part.strip() for part in line.split("=", 1))
                for line in f
                if "=" in line and not line.lstrip().startswith("#")
            )
        self.assertEqual(int(config["first_uid"]), ISOLATE_FIRST_UID)
        self.assertEqual(int(config["num_boxes"]), ISOLATE_BOXES)


class IsolateCmdTestCase(SimpleTestCase):
    LANGUAGES = ["java", "kotlin", "csharp", "python", "cpp"]

    def _cmds(self, lang, time_limit=2, memory_limit=256, box_id=1):
        submission = SimpleNamespace(id=42)
        compiler = SimpleNamespace(
            path="/usr/bin/python3",
            arguments="-O {0}",
            file_extension="py",
            exec_extension="exe",
        )
        isolate = get_cmd_for_language_isolate(
            submission, compiler, lang, time_limit, memory_limit, box_id, "/s/m"
        )
        box_uid = ISOLATE_FIRST_UID + box_id
        safeexec = get_cmd_for_language_safeexec(
            submission, compiler, lang, time_limit, memory_limit, (box_uid, box_uid)
        )
        return isolate, safeexec

    def test_runs_the_usual_safeexec_command_as_the_box_user(self):
        for lang in self.LANGUAGES:
            with self.subTest(lang=lang):
                isolate, safeexec = self._cmds(lang)
                self.assertTrue(isolate.endswith(" --run -- /usr/bin/env " + safeexec))
                self.assertIn("--box-id=1 ", isolate)

    def test_box_limits_are_above_safeexecs(self):
        isolate, _ = self._cmds("cpp", time_limit=2, memory_limit=256)
        self.assertGreater(int(_flag(isolate, "time")), get_clock_limit(2))
        self.assertGreater(int(_flag(isolate, "wall-time")), get_clock_limit(2))
        self.assertGreater(int(_flag(isolate, "cg-mem")), 256 * 1024)
        self.assertEqual(_flag(isolate, "meta"), "/s/m")


class ParseBoxIdTestCase(SimpleTestCase):
    def test_values(self):
        self.assertEqual(parse_box_id(None), 0)
        self.assertEqual(parse_box_id(""), 0)
        self.assertEqual(parse_box_id("1"), 1)

    def test_rejects_what_isolate_would_reject(self):
        for bad in ("a", "-1", "1000"):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    parse_box_id(bad)
