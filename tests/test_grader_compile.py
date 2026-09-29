"""Compilation runs under safeexec as an unprivileged user; see
COMPILE_CPU_LIMIT in api/management/commands/grader.py."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from api.management.commands.grader import (
    VM_COMPILED_LANGUAGES,
    collect_build_outputs,
    get_compile_cmd,
    run_compiler,
)


class CompileCmdTestCase(SimpleTestCase):
    def _cmd(self, language):
        return get_compile_cmd(
            "/opt/gcc-11.3.0/bin/g++",
            "-O2 42.cpp -o 42.exe",
            language,
            12345,
            "/sandbox/42/compile_errors.txt",
        )

    def test_command(self):
        # Pinned to one uid, so the grader can kill what the compile leaves;
        # --error keeps gcc's errors, which safeexec would send to /dev/null.
        self.assertEqual(
            self._cmd("c++"),
            "/usr/local/bin/safeexec --uids 12345 12345 --cpu 60 --clock 120"
            " --mem 2097152 --vmrss --nproc 128 --fsize 524288 --stack 0"
            " --space 2097152 --error"
            ' "/sandbox/42/compile_errors.txt"'
            ' --exec "/opt/gcc-11.3.0/bin/g++" -O2 42.cpp -o 42.exe',
        )

    def test_no_address_space_cap_for_vm_compilers(self):
        for language in VM_COMPILED_LANGUAGES:
            with self.subTest(language=language):
                self.assertNotIn("--space", self._cmd(language))


@unittest.skipUnless(os.geteuid() == 0, "chowns files to root")
class CollectBuildOutputsTestCase(SimpleTestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.build = os.path.join(self.folder, "build")
        os.mkdir(self.build)

    def _write(self, path, content, mode=0o644):
        with open(path, "w") as f:
            f.write(content)
        os.chmod(path, mode)

    def test_moves_plain_files_owned_by_root(self):
        self._write(os.path.join(self.build, "Main.class"), "a")
        self._write(os.path.join(self.build, "Main$1.class"), "b", 0o4777)
        os.chown(os.path.join(self.build, "Main.class"), 12345, 12345)
        collect_build_outputs(self.build, self.folder)
        for name in ("Main.class", "Main$1.class"):
            st = os.stat(os.path.join(self.folder, name))
            self.assertEqual((st.st_uid, st.st_gid), (0, 0))
            self.assertEqual(st.st_mode & 0o7777, 0o755)  # no setuid
        self.assertFalse(os.path.exists(self.build))

    def test_skips_symlinks_and_directories(self):
        os.symlink("/etc/passwd", os.path.join(self.build, "output.txt"))
        os.mkdir(os.path.join(self.build, "META-INF"))
        collect_build_outputs(self.build, self.folder)
        self.assertFalse(os.path.lexists(os.path.join(self.folder, "output.txt")))
        self.assertFalse(os.path.lexists(os.path.join(self.folder, "META-INF")))

    def test_never_replaces_a_file_the_grader_wrote(self):
        self._write(os.path.join(self.folder, "42.cpp"), "original")
        self._write(os.path.join(self.build, "42.cpp"), "replaced")
        collect_build_outputs(self.build, self.folder)
        with open(os.path.join(self.folder, "42.cpp")) as f:
            self.assertEqual(f.read(), "original")


@unittest.skipUnless(os.geteuid() == 0, "chowns the build folder")
class RunCompilerTestCase(SimpleTestCase):
    @mock.patch("api.management.commands.grader.kill_processes_of")
    @mock.patch("api.management.commands.grader.get_exitcode_stdout_stderr")
    def test_compiler_starts_without_supplementary_groups(self, run, _):
        # Otherwise the compiler keeps root's groups; see run_compiler.
        folder = tempfile.mkdtemp()

        def fake_run(cmd, **kwargs):
            open(os.path.join(folder, "compile_errors.txt"), "w").close()
            return 0, "", "OK\n"

        run.side_effect = fake_run
        open(os.path.join(folder, "42.cpp"), "w").close()
        compiler = SimpleNamespace(env=None, path="/bin/true", arguments="{0} {1}")
        run_compiler(compiler, "c++", folder, "42.cpp", "42.exe")
        self.assertEqual(run.call_args.kwargs["extra_groups"], [])
