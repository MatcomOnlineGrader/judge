"""Switch to the ICPC World Finals toolchains (see docker/common/dockerfile.grader).

Each upgraded compiler gets a new row and the old one is deactivated, so past
submissions keep the name of the compiler that judged them. For every new row:

- problems that allowed the old compiler also allow the new one;
- per-problem limits (Problem.multiple_limits, keyed by compiler name) are
  copied from the old name to the new one;
- users who preferred the old compiler now prefer the new one.

"Python 3.9.15 (PyPy 7.3.10)" is a second row for PyPy 7.3.10, and is
upgraded the same way, into the same new row.

CPython isn't offered at the World Finals, so it's deactivated and PyPy takes
its place. Its per-problem limits aren't copied: they were set for CPython,
which is several times slower. Mono stays at 6.12; only its path changed.

Only acts on an installation that has the current compilers, so it does
nothing on a fresh database.
"""

import json

from django.db import migrations

UPGRADES = [
    (
        "g++ (GCC) 11.3.0",
        {
            "language": "C++",
            "name": "g++ (GCC) 13.2.0",
            "path": "/usr/bin/g++",
            "arguments": "-x c++ -g -O2 -std=gnu++20 -static {0} -o {1}",
            "file_extension": "cpp",
            "exec_extension": "out",
        },
    ),
    (
        "gcc (GCC) 11.3.0",
        {
            "language": "C",
            "name": "gcc (GCC) 13.2.0",
            "path": "/usr/bin/gcc",
            "arguments": "-x c -g -O2 -std=gnu11 -static {0} -lm -o {1}",
            "file_extension": "c",
            "exec_extension": "out",
        },
    ),
    (
        "Java (javac 17.0.8)",
        {
            "language": "Java",
            "name": "Java (javac 21.0.4)",
            "path": "/usr/bin/javac",
            "arguments": "-encoding UTF-8 -sourcepath . -d . {0}",
            "file_extension": "java",
            "exec_extension": "out",
        },
    ),
    (
        "Kotlin 1.7.21",
        {
            "language": "Kotlin",
            "name": "Kotlin 1.9.24",
            "path": "/opt/kotlin-1.9.24/bin/kotlinc",
            "arguments": "-d . {0}",
            "file_extension": "kt",
            "exec_extension": "out",
        },
    ),
    (
        "PyPy 7.3.10",
        {
            "language": "Python",
            "name": "PyPy 7.3.15",
            "path": "/usr/bin/pypy3",
            "arguments": "{0}",
            "file_extension": "py",
            "exec_extension": "out",
        },
    ),
]

# Other names of an upgraded compiler: deactivated, with their users,
# problems and limits moved to the new row named second.
ALIASES = [("Python 3.9.15 (PyPy 7.3.10)", "PyPy 7.3.15")]

# Deactivated, with its users and problems moved to the compiler named second.
RETIRED = [("Python 3.9.18", "PyPy 7.3.15")]

CSHARP = "C# Mono 6.12"
CSHARP_OLD_PATH = "/usr/local/bin/csc"
CSHARP_NEW_PATH = "/usr/bin/csc"


def copy_limits(Problem, old_name, new_name):
    for problem in Problem.objects.filter(multiple_limits__contains=old_name):
        try:
            limits = json.loads(problem.multiple_limits)
        except ValueError:
            continue
        if not isinstance(limits, dict) or old_name not in limits:
            continue
        if new_name in limits:
            continue
        limits[new_name] = limits[old_name]
        problem.multiple_limits = json.dumps(limits, indent=4)
        problem.save(update_fields=["multiple_limits"])


def move_users_and_problems(Problem, UserProfile, old, new):
    UserProfile.objects.filter(compiler=old).update(compiler=new)
    Through = Problem.compilers.through
    problem_ids = Through.objects.filter(compiler=old).values_list(
        "problem_id", flat=True
    )
    Through.objects.bulk_create(
        [Through(problem_id=pid, compiler_id=new.id) for pid in problem_ids],
        ignore_conflicts=True,
    )


def retire(Compiler, Problem, UserProfile, old_name, new_name):
    """Deactivates `old_name` and moves its users and problems to `new_name`.
    Returns False, doing nothing, unless both compilers exist."""
    old = Compiler.objects.filter(name=old_name).first()
    new = Compiler.objects.filter(name=new_name).first()
    if old is None or new is None:
        return False
    old.active = False
    old.save(update_fields=["active"])
    move_users_and_problems(Problem, UserProfile, old, new)
    return True


def forwards(apps, schema_editor):
    Compiler = apps.get_model("api", "Compiler")
    Problem = apps.get_model("api", "Problem")
    UserProfile = apps.get_model("api", "UserProfile")

    for old_name, fields in UPGRADES:
        old = Compiler.objects.filter(name=old_name).first()
        if old is None:
            continue
        new, _ = Compiler.objects.get_or_create(
            name=fields["name"], defaults=dict(fields, env=old.env)
        )
        # Also when the row is left over from a rollback, which deactivates it.
        new.active = True
        new.save(update_fields=["active"])
        old.active = False
        old.save(update_fields=["active"])
        move_users_and_problems(Problem, UserProfile, old, new)
        copy_limits(Problem, old_name, new.name)

    for old_name, new_name in ALIASES:
        if retire(Compiler, Problem, UserProfile, old_name, new_name):
            copy_limits(Problem, old_name, new_name)

    for old_name, new_name in RETIRED:
        retire(Compiler, Problem, UserProfile, old_name, new_name)

    Compiler.objects.filter(name=CSHARP, path=CSHARP_OLD_PATH).update(
        path=CSHARP_NEW_PATH
    )


def backwards(apps, schema_editor):
    """Reactivates the old compilers and deactivates the new ones. Copied
    limits, problem links and user preferences are left as they are."""
    Compiler = apps.get_model("api", "Compiler")
    old_names = [old for old, _ in UPGRADES + ALIASES + RETIRED]
    new_names = [fields["name"] for _, fields in UPGRADES]
    if not Compiler.objects.filter(name__in=old_names).exists():
        return
    Compiler.objects.filter(name__in=old_names).update(active=True)
    Compiler.objects.filter(name__in=new_names).update(active=False)
    Compiler.objects.filter(name=CSHARP, path=CSHARP_NEW_PATH).update(
        path=CSHARP_OLD_PATH
    )


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0048_auto_20250923_0316"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
