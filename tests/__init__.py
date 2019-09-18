import datetime
import os
import random
import string

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
import pytz

from api.models import (
    Checker,
    Compiler,
    Contest,
    ContestInstance,
    Post,
    Problem,
    Result,
    Submission,
    Team,
    User,
    UserProfile,
)


TEST_USER_PASSWORD = "XXXXX"


def random_string(length: int) -> str:
    result = ''
    for i in range(length):
        result += random.choice(string.ascii_lowercase)
    return result


class FixturedTestCase(TestCase):
    def updateUserProfile(self, user, **kargs):
        profile = user.profile
        for attr, value in kargs.items():
            setattr(profile, attr, value)
        profile.save()
        return user

    def login(self, user):
        """Log user in using self.client"""
        self.client.login(
            username=user.username,
            password=TEST_USER_PASSWORD
        )

    def newUser(self, username, **kargs):
        default = {
            "username": username,
            "email": username + "@host.com"
        }
        default.update(**kargs)
        user = User.objects.create(**default)
        user.set_password(TEST_USER_PASSWORD)
        user.save()
        return user

    def newAdmin(self, username, **kargs):
        admin = self.newUser(username=username, **kargs)
        return self.updateUserProfile(admin, role="admin")

    def newPost(self, user, **kargs):
        default = {
            "name": "Post name",
            "body": "Post body",
            "meta_description": "Meta description",
            "meta_image": "http://example.com/image.png",
            "user": user,
            "show_in_main_page": False
        }
        default.update(**kargs)
        return Post.objects.create(**default)

    def newContestInstance(self, contest, user, **kargs):
        default = {
            "user": user,
            "contest": contest,
            "real": True,
            "start_date": contest.start_date
        }
        default.update(**kargs)
        return ContestInstance.objects.create(**default)

    def newSubmission(self, instance, user, minutes=60, **kargs):
        default = {
            "user": user,
            "instance": instance,
            "date": instance.start_date + timezone.timedelta(minutes=minutes),
            "compiler": self.py2
        }
        default.update(**kargs)
        return Submission.objects.create(**default)

    def newProblem(self, title, contest, position, **kargs):
        default = {
            "title": title,
            "position": position,
            "contest": contest,
            "time_limit": 0,
            "memory_limit": 0,
        }
        default.update(**kargs)
        problem,_ = Problem.objects.get_or_create(**default)
        return problem

    def newContest(self, **kwargs):
        """
        Create a contest that start in the future and has a duration of
        5 hours.
        """
        NOW = timezone.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        start_date = NOW + datetime.timedelta(hours=4)
        end_date = start_date + datetime.timedelta(hours=5)
        default = {
            "start_date": start_date,
            "end_date": end_date,
            "name": "My Contest",
            "visible": True,
            "closed": False,
            "allow_teams": True,
        }
        default.update(**kwargs)
        return Contest.objects.create(**default)

    def newTeam(self, number_of_users, **kwargs):
        """
        Creates a new team with a given number of users.
        """
        default = {
            "name": "Team name",
            "description": "Team description",
        }
        default.update(**kwargs)
        team = Team.objects.create(**default)
        for k in range(number_of_users):
            user = self.newUser(username=random_string(length=48))
            team.profiles.add(user.profile)
        return team

    def setUp(self):
        JANUARY_ONE_2018 = timezone.datetime(
            year=2018,
            month=1,
            day=1,
            tzinfo=pytz.timezone(settings.TIME_ZONE)
        )

        NOW = timezone.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))

        # <contests>
        self.past_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 1',
            code='DC1',
            visible=True,
            start_date=JANUARY_ONE_2018,
            end_date=JANUARY_ONE_2018 + timezone.timedelta(hours=4),
            needs_unfreeze=False
        )

        self.running_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 2',
            code='DC2',
            visible=True,
            start_date=NOW - timezone.timedelta(hours=1),
            end_date=NOW + timezone.timedelta(hours=3)
        )

        self.coming_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 3',
            code='DC3',
            visible=True,
            start_date=NOW + timezone.timedelta(days=1),
            end_date=NOW + timezone.timedelta(days=1, hours=4)
        )

        self.coming_hidden_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 4',
            code='DC4',
            visible=True,
            start_date=NOW + timezone.timedelta(days=1),
            end_date=NOW + timezone.timedelta(days=1, hours=4)
        )

        self.frozen_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 5',
            code='DC5',
            visible=True,
            start_date=NOW - timezone.timedelta(hours=2),
            end_date=NOW + timezone.timedelta(minutes=30),
            frozen_time=45
        )

        self.death_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 6',
            code='DC6',
            visible=True,
            start_date=NOW - timezone.timedelta(hours=2),
            end_date=NOW + timezone.timedelta(minutes=10),
            death_time=15
        )

        self.past_frozen_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 7',
            code='DC7',
            visible=True,
            start_date=JANUARY_ONE_2018,
            end_date=JANUARY_ONE_2018 + timezone.timedelta(hours=4)
        )

        self.coming_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 8',
            code='DC8',
            visible=True,
            start_date=NOW + timezone.timedelta(hours=4),
            end_date=NOW + timezone.timedelta(hours=8)
        )

        # <problems>
        self.problem1, _ = Problem.objects.get_or_create(
            title='A*B',
            time_limit=0,
            memory_limit=0,
            position=1,
            contest=self.past_contest
        )

        self.problem2, _ = Problem.objects.get_or_create(
            title='A*B',
            time_limit=0,
            memory_limit=0,
            position=1,
            contest=self.running_contest
        )

        # <checkers>
        self.wcmp, _ = Checker.objects.get_or_create(
            name='wcmp',
            description='Compare sequences of tokens',
            backend="testlib.h",
            source=open(os.path.join(settings.BASE_DIR, 'tests/checkers/wcmp.cpp'), 'r').read()
        )

        # <results>
        self.accepted, _ = Result.objects.get_or_create(
            name='Accepted',
            color='green',
            penalty=False
        )

        self.memory_limit_exceeded, _ = Result.objects.get_or_create(
            name='Memory Limit Exceeded',
            color='red',
            penalty=True
        )

        self.pending, _ = Result.objects.get_or_create(
            name='Pending',
            color='orange',
            penalty=False
        )

        self.runtime_error, _ = Result.objects.get_or_create(
            name='Runtime Error',
            color='red',
            penalty=True
        )

        self.time_limit_exceeded, _ = Result.objects.get_or_create(
            name='Time Limit Exceeded',
            color='red',
            penalty=True
        )

        self.wrong_answer, _ = Result.objects.get_or_create(
            name='Wrong Answer',
            color='red',
            penalty=True
        )

        self.compilation_error, _ = Result.objects.get_or_create(
            name='Compilation Error',
            color='blue',
            penalty=False
        )


        # <compilers>
        self.py2, _ = Compiler.objects.get_or_create(
            language='Python2',
            name='Python 2.7.9',
            path='python2',
            arguments='-O {0}',
            file_extension='py',
            exec_extension='py',
        )

        self.py3, _ = Compiler.objects.get_or_create(
            language='Python3',
            name='Python 3.5.6',
            path='python3',
            arguments='-O {0}',
            file_extension='py',
            exec_extension='py',
        )

        self.cpp, _ = Compiler.objects.get_or_create(
            language='CPP',
            name='GNU C++ 5.1.0',
            path='g++',
            arguments='-static -fno-optimize-sibling-calls -fno-strict-aliasing -DMOG -lm -s -x c++ -Wl,--stack=268435456 -O2 {0} -o {1}',
            file_extension='cpp',
            exec_extension='exe',
        )

        # attach compilers to problems
        self.problem1.compilers.add(self.cpp)
        self.problem1.compilers.add(self.py2)
        self.problem1.compilers.add(self.py3)

        self.problem2.compilers.add(self.cpp)
        self.problem2.compilers.add(self.py2)
        self.problem2.compilers.add(self.py3)
