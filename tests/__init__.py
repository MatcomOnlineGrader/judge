import os
import string

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
import pytz

from api.models import Checker, Compiler, Contest, Post, Result, User, UserProfile


class FixturedTestCase(TestCase):
    def updateUserProfile(self, user, **kargs):
        profile = user.profile
        for attr, value in kargs.items():
            setattr(profile, attr, value)
        profile.save()
        return user

    def newUser(self, username, **kargs):
        default = {
            "username": username,
            "email": username + "@host.com"
        }
        default.update(**kargs)
        return User.objects.create(**default)

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

    def setUp(self):
        JANUARY_ONE_2018 = timezone.datetime(
            year=2018,
            month=1,
            day=1,
            tzinfo=pytz.timezone(settings.TIME_ZONE)
        )

        # <contests>
        self.past_contest, _ = Contest.objects.get_or_create(
            name='Dummy Contest # 1',
            code='DC1',
            visible=True,
            start_date=JANUARY_ONE_2018,
            end_date=JANUARY_ONE_2018 + timezone.timedelta(hours=4)
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
