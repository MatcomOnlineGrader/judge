"""
End-to-end check of the grader in the local environment.

Submits a catalog of programs with known verdicts to the A+B problem created by
`populate_local_dev`, waits for the running grader to judge them, and reports
which ones got an unexpected verdict. Exits with status 1 on any mismatch.

```bash
export MOG_LOCAL_DEV=1
python manage.py populate_local_dev --recreate
python manage.py grader_e2e                  # every case
python manage.py grader_e2e --only tle       # cases whose name contains "tle"
python manage.py grader_e2e --exclude csharp # skip cases whose name contains "csharp"
```

On Apple Silicon the grader runs under amd64 emulation, where Mono aborts
(`tramp-amd64.c` assertion) for any C# program, so `csharp-ac` fails there.

Like `populate_local_dev`, it refuses to run unless MOG_LOCAL_DEV=1.
"""

import os
import re

from django.contrib.auth.models import User
from django.core.management import BaseCommand, CommandError
from django.utils import timezone

from api.models import Compiler, Problem, Result, Submission

from .rejudge_compare import wait_for_grader

# A+B: one line "a b", answer a + b.
CPP_AC = r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; std::cout << a + b << "\n"; }
"""

# Burns ~850ms of CPU against the 1s limit, measured with clock() so it lands
# just under the limit on any machine. Before the --clock fix this flapped
# between Accepted and Time Limit Exceeded depending on host load.
CPP_NEAR_LIMIT = r"""
#include <ctime>
#include <iostream>
int main() {
    long long a, b;
    std::cin >> a >> b;
    volatile long long sink = 0;
    while (clock() < 0.85 * CLOCKS_PER_SEC)
        for (int i = 0; i < 10000; i++) sink = sink + i;
    std::cout << a + b << "\n";
}
"""

CPP_TLE = r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; volatile long long x = 0; for (;;) x = x + 1; }
"""

CPP_WA = r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; std::cout << a - b << "\n"; }
"""

CPP_RE = r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; return 3; }
"""

CPP_CE = "int main() { this is not c++ }"

C_AC = r"""
#include <stdio.h>
int main(void) { long long a, b; scanf("%lld %lld", &a, &b); printf("%lld\n", a + b); return 0; }
"""

PY_AC = "a, b = map(int, input().split())\nprint(a + b)\n"

PY_TLE = "while True:\n    pass\n"

# Sleeps well past the 1s limit while using almost no CPU. The CPU limit is
# authoritative, so this is Accepted; on master the equal wall clock made it
# Time Limit Exceeded.
PY_SLEEP_AC = (
    "import time\n"
    "a, b = map(int, input().split())\n"
    "time.sleep(1.5)\n"
    "print(a + b)\n"
)

JAVA_AC = r"""
import java.util.Scanner;
public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        long a = in.nextLong(), b = in.nextLong();
        System.out.println(a + b);
    }
}
"""

# Uses no CPU, so only the wall clock can stop it.
JAVA_SLEEP_TLE = r"""
public class Main {
    public static void main(String[] args) throws Exception {
        Thread.sleep(Long.MAX_VALUE);
    }
}
"""

KOTLIN_AC = """
fun main() {
    val (a, b) = readLine()!!.trim().split(" ").map { it.toLong() }
    println(a + b)
}
"""

CSHARP_AC = r"""
using System;
class Program {
    static void Main() {
        var p = Console.ReadLine().Trim().Split(' ');
        Console.WriteLine(long.Parse(p[0]) + long.Parse(p[1]));
    }
}
"""

# (name, compiler, source, expected verdict)
CASES = [
    ("cpp-ac", "c++", CPP_AC, "Accepted"),
    ("cpp-near-limit-ac", "c++", CPP_NEAR_LIMIT, "Accepted"),
    ("cpp-tle", "c++", CPP_TLE, "Time Limit Exceeded"),
    ("cpp-wa", "c++", CPP_WA, "Wrong Answer"),
    ("cpp-re", "c++", CPP_RE, "Runtime Error"),
    ("cpp-ce", "c++", CPP_CE, "Compilation Error"),
    ("c-ac", "c", C_AC, "Accepted"),
    ("python-ac", "python", PY_AC, "Accepted"),
    ("python-tle", "python", PY_TLE, "Time Limit Exceeded"),
    ("python-sleep-ac", "python", PY_SLEEP_AC, "Accepted"),
    ("pypy-ac", "pypy", PY_AC, "Accepted"),
    ("java-ac", "java", JAVA_AC, "Accepted"),
    ("java-sleep-tle", "java", JAVA_SLEEP_TLE, "Time Limit Exceeded"),
    ("kotlin-ac", "kotlin", KOTLIN_AC, "Accepted"),
    ("csharp-ac", "c#", CSHARP_AC, "Accepted"),
]

# Judgement details are shown to users; internal measurements such as the CPU
# time used before a TLE belong in the grader log, not here.
LEAKED_DETAILS = re.compile(r"\bcpu\b", re.IGNORECASE)


class Command(BaseCommand):
    help = "Submit programs with known verdicts and check the grader judges them correctly."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            default="",
            help="Only run cases whose name contains this text.",
        )
        parser.add_argument(
            "--exclude",
            default=None,
            help="Skip cases whose name contains this text.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=1200,
            help="Seconds to wait for the grader before giving up.",
        )
        parser.add_argument(
            "--user",
            default="alice",
            help="User the submissions are made as.",
        )

    def handle(self, *args, **options):
        if os.environ.get("MOG_LOCAL_DEV", "0") != "1":
            raise CommandError(
                "Refusing to run: set MOG_LOCAL_DEV=1 (local environment only)."
            )

        try:
            problem = Problem.objects.get(title="A+B")
            user = User.objects.get(username=options["user"])
            pending = Result.objects.get(name__iexact="pending")
        except Exception as e:
            raise CommandError(
                "Missing fixtures (%s). Run `populate_local_dev --recreate` first." % e
            )

        cases = [
            c
            for c in CASES
            if options["only"] in c[0]
            and not (options["exclude"] and options["exclude"] in c[0])
        ]
        if not cases:
            raise CommandError("No case matches --only %r" % options["only"])

        compilers = {c.name: c for c in Compiler.objects.all()}
        missing = sorted({c[1] for c in cases} - set(compilers))
        if missing:
            raise CommandError(
                "Compiler(s) %s missing. Run `populate_local_dev --recreate`."
                % ", ".join(missing)
            )

        submitted = []
        for name, compiler_name, source, expected in cases:
            submission = Submission.objects.create(
                problem=problem,
                date=timezone.now(),
                source=source,
                user=user,
                result=pending,
                compiler=compilers[compiler_name],
            )
            submitted.append((submission.id, name, expected))
        self.stdout.write(
            "Submitted %d case(s) as #%d-#%d. Waiting for the grader..."
            % (len(submitted), submitted[0][0], submitted[-1][0])
        )

        ids = [s[0] for s in submitted]

        def report(judged):
            if judged:
                self.stdout.write("  %d/%d judged" % (judged, len(ids)))

        remaining = wait_for_grader(ids, options["timeout"], 5, report)

        results = Submission.objects.select_related("result").in_bulk(ids)
        failures = 0
        self.stdout.write("")
        for sid, name, expected in submitted:
            submission = results[sid]
            got = submission.result.name
            details = (submission.judgement_details or "").strip()
            ok = got.lower() == expected.lower()
            if ok and LEAKED_DETAILS.search(details):
                ok = False
                got += " (details expose internal CPU measurements)"
            failures += not ok
            self.stdout.write(
                "%s  #%-4d %-20s expected %-20s got %s"
                % ("PASS" if ok else "FAIL", sid, name, expected, got)
            )
            if not ok and details:
                first = details.splitlines()[0]
                self.stdout.write("        %s" % first[:200])

        self.stdout.write("")
        if remaining:
            self.stdout.write(
                "%d case(s) were still unjudged after %ds."
                % (remaining, options["timeout"])
            )
        self.stdout.write(
            "%d passed, %d failed" % (len(submitted) - failures, failures)
        )
        if failures:
            raise SystemExit(1)
