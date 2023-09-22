"""
This command is to populate the local environment with enough data to make some manual tests.
Since running this command in production environment is a security risk (creates admin user with password admin),
it is required to set manually the variable MOG_LOCAL_DEV to 1.

```bash
export MOG_LOCAL_DEV=1
```

It creates the following elements:

Users:
  - admin:admin (With admin privilege)
  - judge:judge (Judge privilege for Contest #1)
  - observer:observer (Observer privilege for Contest #1)
  - user:user (Regular user)

Checker:
  - wcmp: Standard checker compiled for your platform.

Problem:
  - A + B: Standard problem with several test-cases.

Contest:
  - Contest #1: Contest with problem A + B

Institution:
  - Earth

Compilers:
  - Python
  - C++
  - Java
"""
import os
import random
from functools import partial
from json import dumps
from os import makedirs
from pathlib import Path
from shutil import rmtree, copy2

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand
from django.utils import timezone

from api.models import (
    Checker,
    Compiler,
    Contest,
    Institution,
    Problem,
    Result,
    UserProfile,
)

USERS = [
    {"name": "admin", "role": "admin"},
    {
        "name": "observer",
        "role": "observer",
    },
    {
        "name": "judge",
        "role": "judge",
    },
    {
        "name": "alice",
        "role": None,
    },
]

COMPILERS = [
    {
        "language": "python",
        "name": "python",
        "arguments": "-O {0}",
        "path": "python",
        "file_extension": "py",
        "exec_extension": "exe",
    },
    {
        "language": "java",
        "name": "java",
        "arguments": '-cp ".;*" {0}',
        "path": "javac",
        "file_extension": "java",
        "exec_extension": "exe",
    },
    {
        "language": "c++",
        "name": "c++",
        "arguments": "-static -fno-optimize-sibling-calls -fno-strict-aliasing -DMOG -lm -s -x c++ -Wl,--stack=268435456 -O2 -std=c++11 -D__USE_MINGW_ANSI_STDIO=0 {0} -o {1}",
        "path": "g++",
        "file_extension": "cpp",
        "exec_extension": "exe",
    },
]

RESULTS = [
    ("Idleness Limit Exceeded", "red", True),
    ("Disqualified", "red", True),
    ("Internal Error", "blue", False),
    ("Compilation Error", "blue", False),
    ("Runtime Error", "red", True),
    ("Compiling", "orange", False),
    ("Running", "orange", False),
    ("Pending", "orange", False),
    ("Memory Limit Exceeded", "red", True),
    ("Time Limit Exceeded", "red", True),
    ("Wrong Answer", "red", True),
    ("Accepted", "green", False),
]


def generate_test_cases():
    rnd = random.Random("A + B")
    A = rnd.sample(range(10), 10)
    B = rnd.sample(range(10), 10)
    ins = []
    outs = []

    for a, b in zip(A, B):
        ins.append(f"{a} {b}\n")
        outs.append(f"{a + b}\n")

    return ins[:2], outs[:2], ins[2:], outs[2:]


def remove(instance, dry):
    if instance is None:
        return

    print("Delete:", instance)
    if not dry:
        instance.delete()


def create(instance, dry):
    if instance is None:
        return

    print("Create:", instance)
    if not dry:
        instance.save()


def apply(current_instance, new_instance, dry, reset):
    if reset:
        try:
            instance = current_instance()
        except ObjectDoesNotExist:
            instance = None
        remove(instance, dry)
    else:
        try:
            instance = current_instance()
            instance = None
        except ObjectDoesNotExist:
            instance = new_instance()
        create(instance, dry)


def read_from(path):
    with open(path) as f:
        content = f.read()
    return content


class ProblemWrapper:
    def __init__(self, problem):
        self.problem = problem

    def save(self):
        self.problem.save()

        # Compiler can only be set after the problem have an id.
        for compiler in Compiler.objects.all():
            self.problem.compilers.add(compiler)

        # Generate testcases
        sample_in, sample_out, full_in, full_out = generate_test_cases()

        # Save sample testcases
        samples = {}
        for ix, (s_in, s_out) in enumerate(zip(sample_in, sample_out)):
            samples[str(ix)] = {"in": s_in, "out": s_out}
        self.problem.samples = dumps(samples)
        self.problem.save()

        # Save testcases
        problem = Path(settings.PROBLEMS_FOLDER) / str(self.problem.id)
        ins = problem / "inputs"
        outs = problem / "outputs"
        makedirs(ins, exist_ok=True)
        makedirs(outs, exist_ok=True)
        for ix, (f_in, f_out) in enumerate(zip(full_in, full_out)):
            r_ix = ix + len(sample_in)
            with open(ins / f"{r_ix}.in", "w") as f:
                f.write(f_in)
            with open(outs / f"{r_ix}.out", "w") as f:
                f.write(f_out)

    def delete(self):
        # Delete all testcases
        problem = Path(settings.PROBLEMS_FOLDER) / str(self.problem.id)
        try:
            rmtree(problem)
        except FileNotFoundError:
            pass
        self.problem.delete()

    def __str__(self):
        return self.problem.__str__()


def create_aplusb():
    problem = Problem(
        title="A+B",
        body="A+B",
        time_limit=1,
        memory_limit=1024,
        position=1,
        contest_id=Contest.objects.get(name="test01").id,
        checker=Checker.objects.get(name="wcmp"),
    )
    return ProblemWrapper(problem)


class UserWrapper:
    def __init__(self, user_profile):
        self.user_profile = user_profile
        self.user = user_profile.user

    def save(self):
        user = User.objects.create_user(
            username=self.user.username,
            password=self.user.password,
            email=self.user.email,
        )
        self.user_profile.user = user
        self.user_profile.save()

    def delete(self):
        self.user_profile.delete()
        self.user.delete()

    def __str__(self):
        return self.user_profile.__str__() + " | " + self.user.__str__()


def create_user(name, role):
    user = User(
        username=name,
        password=name,
        email=f"{name}@mog.com",
    )

    if role == "admin":
        user.is_staff = True

    user_profile = UserProfile(user=user, role=role)

    return UserWrapper(user_profile)


class Command(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "-d",
            "--no-dry",
            action="store_true",
            default=False,
            help="Without this argument it shows the implications this command will have without running it. In no-dry mode it will apply the changes",
        )
        parser.add_argument(
            "-r",
            "--reset",
            action="store_true",
            default=False,
            help="Rollback all changes done by this command.",
        )

    def handle(self, *args, **options):
        print(
            "WARNING: Running this command in PRODUCTION can be a security risk! DON'T DO IT."
        )

        if os.environ.get("MOG_LOCAL_DEV", "0") != "1":
            print(
                "To run this command you need to explicitely set environment variable:"
            )
            print("MOG_LOCAL_DEV=1")
            exit(1)

        dry = not options["no_dry"]
        reset = options["reset"]
        _apply = partial(apply, dry=dry, reset=reset)

        # Copy / Delete testlib.h
        if reset:
            try:
                print("Delete: testlib.h")
                if not dry:
                    os.unlink(Path(settings.RESOURCES_FOLDER) / "testlib.h")
            except FileNotFoundError:
                pass
        else:
            print("Create: testlib.h")
            if not dry:
                copy2(
                    Path("resources") / "testlib.h",
                    Path(settings.RESOURCES_FOLDER) / "testlib.h",
                )

        if reset:
            # Problem needs to be removed first, otherwise it is removed on cascade mode.
            _apply(
                lambda: ProblemWrapper(Problem.objects.get(title="A+B")), create_aplusb
            )

        _apply(
            lambda: Institution.objects.get(name="Earth"),
            lambda: Institution(name="Earth", url="earth.org"),
        )

        _apply(
            lambda: Contest.objects.get(name="test01"),
            lambda: Contest(
                name="test01",
                code="test01",
                start_date=timezone.now(),
                end_date=timezone.now(),
            ),
        )

        _apply(
            lambda: Checker.objects.get(name="wcmp"),
            lambda: Checker(
                name="wcmp",
                description="Token comparator checker",
                source=read_from("tests/checkers/wcmp.cpp"),
                backend="testlib.h",
            ),
        )

        for compiler in COMPILERS:
            _apply(
                lambda: Compiler.objects.get(name=compiler["name"]),
                lambda: Compiler(**compiler),
            )

        if not reset:
            # Problem needs to be created at the end, after compiler and contest exists.
            _apply(
                lambda: ProblemWrapper(Problem.objects.get(title="A+B")), create_aplusb
            )

        for user in USERS:
            _apply(
                lambda: UserWrapper(
                    UserProfile.objects.get(
                        user=User.objects.get(username=user["name"])
                    )
                ),
                partial(create_user, **user),
            )

        for result, color, penalty in RESULTS:
            _apply(
                lambda: Result.objects.get(name=result),
                lambda: Result(
                    name=result, description=result, color=color, penalty=penalty
                ),
            )
