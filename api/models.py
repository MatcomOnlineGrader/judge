import os
import re
import cgi
import uuid
import json

from django.core.mail import send_mail
from django.db.models import F
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce, Lower

from django.template.loader import render_to_string

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.utils.deconstruct import deconstructible
from django.utils.safestring import mark_safe
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from mog.tasks import report_clarification
from mog.gating import (
    get_all_contest_for_judge,
    user_is_admin,
    user_is_judge_in_contest,
    user_is_observer_in_contest,
)


@deconstructible
class UUIDImageName(object):
    def __init__(self, upload_to):
        self.upload_to = upload_to

    def __call__(self, instance, filename):
        extension = "." + filename.split(".")[-1].lower()
        if extension not in [".jpg", ".jpeg", ".png", ".gif"]:
            extension = ".png"
        return os.path.join(self.upload_to, "%s%s" % (str(uuid.uuid4()), extension))


class Country(models.Model):
    class Meta:
        verbose_name_plural = "Countries"

    name = models.CharField(verbose_name="Country Name", max_length=64)
    flag = models.CharField(verbose_name="Country Flag URL", max_length=128)

    def __str__(self):
        return self.name

    def flag_image_tag(self):
        return mark_safe('<img src="%s" alt="%s">' % (self.flag, self.name))

    flag_image_tag.short_description = "Flag Image"


class Team(models.Model):
    name = models.CharField(max_length=100)
    institution = models.ForeignKey(
        "Institution", null=True, blank=True, on_delete=models.SET_NULL
    )
    description = models.TextField(null=True)
    icpcid = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name=_(
            "ID that links this team to the ICPC, we get this value down from baylor"
        ),
    )

    def __str__(self):
        return "{0} ({1})".format(
            self.name,
            ", ".join([profile.user.username for profile in self.profiles.all()]),
        )


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def get_visible_problems(self, admin=False):
        return self.problems if admin else self.problems.filter(contest__visible=True)

    def __str__(self):
        return self.name


class Checker(models.Model):
    BACKEND_CHOICES = [
        ("testlib.h", "testlib.h (0.9.10-SNAPSHOT)"),
        ("testlib-0.9.42-SNAPSHOT.h", "testlib.h (0.9.42-SNAPSHOT)"),
        ("testlib4j.jar", "testlib4j.jar"),
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    source = models.TextField()
    backend = models.CharField(
        max_length=32, choices=BACKEND_CHOICES, default="testlib.h"
    )

    def __str__(self):
        return self.name


class Contest(models.Model):
    name = models.CharField(max_length=100, unique=False)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    visible = models.BooleanField(default=False)
    needs_unfreeze = models.BooleanField(default=True)
    frozen_time = models.IntegerField(verbose_name="Frozen time (minutes)", default=0)
    death_time = models.IntegerField(verbose_name="Death time (minutes)", default=0)
    closed = models.BooleanField(verbose_name="Closed registration", default=False)
    allow_teams = models.BooleanField(verbose_name="Allow teams", default=False)
    rated = models.BooleanField(default=False)
    group = models.CharField(
        max_length=64, blank=True, null=True, verbose_name=_("Default group")
    )

    def __str__(self):
        return self.name

    def can_be_seen_by(self, user):
        """
        > problems
        > standings
        > submissions
        > submit
        """
        return (
            user_is_admin(user)
            or user_is_judge_in_contest(user, self)
            or (self.visible and not self.is_coming)
        )

    def overview_can_be_seen_by(self, user):
        return (
            self.visible or user_is_admin(user) or user_is_judge_in_contest(user, self)
        )

    def can_be_edited_by(self, user):
        return user_is_admin(user)

    def can_show_saris_to(self, user):
        return (
            user_is_admin(user)
            or user_is_judge_in_contest(user, self)
            or (
                self.visible
                and not self.is_coming
                and user_is_observer_in_contest(user, self)
            )
        )

    @property
    def seconds_until_start(self):
        return max((self.start_date - timezone.now()).total_seconds(), 1)

    @property
    def relative_time(self):
        return timezone.now() - self.start_date

    @property
    def remaining_time(self):
        return self.duration - self.relative_time

    @property
    def percent(self):
        return (
            (timezone.now() - self.start_date).total_seconds()
            * 100
            // self.duration.total_seconds()
        )

    @property
    def duration(self):
        return self.end_date - self.start_date

    @property
    def is_coming(self):
        return timezone.now() < self.start_date

    @property
    def is_past(self):
        return self.end_date < timezone.now()

    def is_running_at(self, timestamp):
        return self.visible and self.start_date <= timestamp <= self.end_date

    @property
    def is_running(self):
        return self.is_running_at(timezone.now())

    def real_registration(self, user):
        """Return the real instance related with this contest and a given user"""
        if not user.is_authenticated:
            return None
        return self.instances.filter(
            Q(real=True) & (Q(user=user) | Q(team__in=user.profile.teams.all()))
        ).first()

    def virtual_registration(self, user):
        """Return the virtual instance related with this contest and a given user"""
        if not user.is_authenticated:
            return None
        return self.instances.filter(
            Q(real=False) & (Q(user=user) | Q(team__in=user.profile.teams.all()))
        ).first()

    def registration(self, user):
        return self.real_registration(user) or self.virtual_registration(user)

    def registered_for_real(self, user):
        return self.real_registration(user) is not None

    def registered_for_virtual(self, user):
        return self.virtual_registration(user) is not None

    def can_register_for_real(self, user, bypass_closed=False):
        """
        User can register in contest for real
        competition if the following five conditions
        hold:
        1) Contest is coming or running.
        2) Contest is open for registration.
        3) User is not admin neither code browser neither observer neither judge.
        4) User is not registered (individually or in a team).
        """
        if self.is_past or (self.closed and not bypass_closed):
            return False
        if (
            user_is_admin(user)
            or user_is_judge_in_contest(user, self)
            or user_is_observer_in_contest(user, self)
        ):
            return False
        return not self.registered_for_real(user)

    def is_virtual_running(self, user):
        raise NotImplementedError()

    def is_virtual_coming(self, user):
        raise NotImplementedError()

    def is_virtual_past(self, user):
        raise NotImplementedError()

    def can_register_for_virtual(self, user):
        """
        User can register in contest for virtual
        competition if the following four conditions
        hold:
        1) Contest is already finished and unfrozen.
        2) User is not admin neither code browser.
        3) User is not registered (individually or in a team).
        """
        if not self.is_past or self.needs_unfreeze:
            return False
        if (
            user_is_admin(user)
            or user_is_judge_in_contest(user, self)
            or user_is_observer_in_contest(user, self)
        ):
            return False
        return not self.registered_for_virtual(user)

    def virtual_percent(self, user):
        raise NotImplementedError()

    @property
    def get_problems(self):
        return self.problems.order_by("position")

    def death_time_from_date(self, date):
        return (
            self.end_date - timezone.timedelta(minutes=self.death_time)
            <= date
            <= self.end_date
        )

    @property
    def is_death_time(self):
        return self.death_time_from_date(timezone.now())

    def frozen_time_from_date(self, date):
        if self.death_time_from_date(date):
            # Check we are not in death time
            return False
        return (
            self.end_date - timezone.timedelta(minutes=self.frozen_time)
            <= date
            <= self.end_date
        )

    @property
    def is_frozen_time(self):
        return self.frozen_time_from_date(timezone.now())

    def visible_clarifications(self, user):
        if user_is_admin(user) or user_is_judge_in_contest(user, self):
            return self.clarifications.order_by("-asked_date")
        if user.is_authenticated:
            return self.clarifications.filter(Q(public=True) | Q(sender=user)).order_by(
                "-asked_date"
            )
        return self.clarifications.filter(public=True).order_by("-asked_date")

    def unseen_clarifications(self, user):
        if user.is_authenticated:
            clarifications = (
                self.clarifications
                if user_is_admin(user)
                else self.clarifications.filter(Q(public=True) | Q(sender=user))
            )
            return clarifications.filter(
                ~Q(pk__in=user.seen_clarifications.all())
            ).count()

    @staticmethod
    def get_all_contests(user):
        if user_is_admin(user):
            queryset = Contest.objects
        else:
            contest_ids = get_all_contest_for_judge(user)
            if contest_ids:
                queryset = Contest.objects.filter(
                    Q(visible=True) | Q(id__in=contest_ids)
                )
            else:
                queryset = Contest.objects.filter(Q(visible=True))

        now = timezone.now()
        running = queryset.filter(start_date__lte=now, end_date__gte=now).order_by(
            "start_date"
        )
        coming = queryset.filter(start_date__gt=now).order_by("start_date")
        past = queryset.filter(end_date__lt=now).order_by("-start_date")

        return running, coming, past

    def group_names(self, include_virtual=False):
        qs = self.instances
        if not include_virtual:
            qs = qs.filter(real=True)

        return list(
            qs.order_by(Lower("group")).values_list("group", flat=True).distinct()
        )


class Problem(models.Model):
    LETTER_COLOR_CHOICES = [("#ffffff", "white"), ("#000000", "black")]
    title = models.CharField(max_length=100)
    body = models.TextField(blank=True)
    input = models.TextField(blank=True)
    output = models.TextField(blank=True)
    hints = models.TextField(null=True, blank=True)
    time_limit = models.PositiveIntegerField(verbose_name="Time limit (s)")
    memory_limit = models.PositiveIntegerField(verbose_name="Memory limit (MB)")
    multiple_limits = models.TextField(
        blank=True, verbose_name="JSON with memory & time limit per compiler"
    )
    tags = models.ManyToManyField(Tag, related_name="problems", blank=True)
    checker = models.ForeignKey(Checker, null=True, on_delete=models.SET_NULL)
    position = models.IntegerField()
    points = models.IntegerField(default=10)
    balloon = models.CharField(
        verbose_name="Balloon color", max_length=50, null=True, blank=True
    )
    letter_color = models.CharField(
        max_length=20, choices=LETTER_COLOR_CHOICES, default="#ffffff"
    )
    contest = models.ForeignKey(
        Contest, related_name="problems", on_delete=models.CASCADE
    )
    slug = models.SlugField(max_length=100, null=True)
    compilers = models.ManyToManyField("Compiler")
    samples = models.TextField(
        null=True, blank=True, verbose_name="Sample inputs/outputs"
    )
    is_html = models.BooleanField(
        default=True,
        verbose_name=_(
            "If true, the problem source is written in Text Rich Editor, else with Simple Markdown Editor."
        ),
    )

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super(Problem, self).save(*args, **kwargs)

    def _visible_submissions(self):
        return self.submissions.filter(
            Q(hidden=False) & (Q(instance=None) | Q(instance__contest__visible=True))
        )

    def _accepted_submissions(self):
        return self._visible_submissions().filter(
            result__name__iexact="accepted", status="normal"
        )

    def _get_limits_json(self):
        try:
            limits = json.loads(self.multiple_limits.strip())
        except:
            limits = None
        return limits

    def time_limit_for_compiler(self, compiler):
        compiler_key = compiler.name
        limits = self._get_limits_json()
        if limits and compiler_key in limits and "Time" in limits[compiler_key]:
            return limits[compiler_key]["Time"]
        return self.time_limit

    def memory_limit_for_compiler(self, compiler):
        compiler_key = compiler.name
        limits = self._get_limits_json()
        if limits and compiler_key in limits and "Memory" in limits[compiler_key]:
            return limits[compiler_key]["Memory"]
        return self.memory_limit

    @staticmethod
    def get_visible_problems(admin=False):
        return (
            Problem.objects if admin else Problem.objects.filter(contest__visible=True)
        )

    @property
    def letter(self):
        if self.position < 1 or self.position > 26:
            return "?"
        return chr(ord("A") + self.position - 1)

    @property
    def code(self):
        return self.contest.code + self.letter

    @property
    def full_title(self):
        return self.letter + " - " + self.title

    @property
    def user_submitted(self):
        """Number of users that have at least one submission to this problem"""
        return self._visible_submissions().distinct("user_id").count()

    @property
    def accepted_submissions(self):
        """Number of accepted submissions"""
        return self._accepted_submissions().count()

    @property
    def total_submissions(self):
        """Total number of submissions"""
        return self._visible_submissions().count()

    @property
    def unique_users_solved(self):
        """Return number of contestant whom solved this problem"""
        return self._accepted_submissions().distinct("user_id").count()

    def total_solved_relevant_for_instance(self, instance):
        if instance and not instance.real and instance.is_running:
            """Return number of contestants whom solved this problem in a real contest including virtual
            participations"""

            real_count = (
                self._accepted_submissions()
                .filter(
                    instance__real=True,
                    date__lte=self.contest.start_date + instance.relative_time,
                )
                .distinct("instance_id")
                .count()
            )

            virtual_count = (
                self._accepted_submissions()
                .filter(
                    instance__real=False,
                    date__lte=F("instance__start_date") + instance.relative_time,
                )
                .distinct("instance_id")
                .count()
            )

            return real_count + virtual_count
        else:
            """Return number of contestants whom solved this problem in a real contest"""
            return (
                self._accepted_submissions()
                .filter(instance__real=True)
                .distinct("instance_id")
                .count()
            )

    """
    @property
    def points(self):
        return 108 / (12 + self.solved) + 1
    """

    @property
    def languages_by_relevance(self):
        def relevance(language):
            return {
                "c": 0,
                "cpp": 1,
                "c++": 2,
                "java": 3,
                "python": 4,
                "python2": 5,
                "python3": 6,
                "kotlin": 7,
                "csharp": 8,
                "c#": 9,
            }.get(language.lower(), 4)

        return sorted(
            set([compiler.language for compiler in self.compilers.all()]), key=relevance
        )

    @property
    def first_compilers(self):
        languages = self.languages_by_relevance
        return ", ".join(languages[:4]) + (", ..." if len(languages) > 4 else "")

    @property
    def compilers2str(self):
        return "<br>".join(
            [
                "%s (%d s, %d MiB)"
                % (
                    compiler.name,
                    self.time_limit_for_compiler(compiler),
                    self.memory_limit_for_compiler(compiler),
                )
                for compiler in self.compilers.all()
            ]
        )

    def __str__(self):
        return self.title


class Post(models.Model):
    name = models.CharField(max_length=250)
    body = models.TextField(blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    show_in_main_page = models.BooleanField(default=False)
    slug = models.SlugField(max_length=250, null=True)
    meta_description = models.CharField(max_length=1024, null=True)
    meta_image = models.CharField(max_length=512, null=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Post, self).save(*args, **kwargs)

    def can_be_edited_by(self, user, admin=False):
        return admin or self.user == user

    def unseen_comments(self, user):
        return Comment.objects.filter(
            Q(post=self), ~Q(pk__in=user.seen_comments.all())
        ).count()

    def update_seen_comments(self, user):
        unseen_comments = Comment.objects.filter(
            Q(post=self), ~Q(pk__in=user.seen_comments.all())
        )
        for comment in unseen_comments.all():
            comment.seen.add(user)

    def can_be_commented_by(self, user):
        """
        A user can comment on a post if the user is active and has some
        problem accepted (the number of points should be positive).
        """
        return (
            user.is_authenticated
            and user.is_active
            and hasattr(user, "profile")
            and user.profile.points > 0
        )

    @property
    def sorted_comments(self):
        return self.comments.order_by("-date").all()

    def __str__(self):
        return self.name


class Message(models.Model):
    source = models.ForeignKey(
        User, related_name="messages_sent", on_delete=models.CASCADE
    )
    target = models.ForeignKey(
        User, related_name="messages_received", on_delete=models.CASCADE
    )
    subject = models.CharField(max_length=250)
    body = models.TextField()
    date = models.DateTimeField(auto_now=True)
    saw = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        super(Message, self).save(*args, **kwargs)
        send_mail(
            "{0} sent you a message".format(self.source.username),
            message="<NO TEXT>",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[self.target.email],
            fail_silently=True,
            html_message=render_to_string(
                "mog/email/message_notification.html",
                {"message": self, "domain": "http://matcomgrader.com"},
            ),
        )


class Division(models.Model):
    title = models.CharField(max_length=50)
    color = models.CharField(max_length=50)
    rating = models.PositiveIntegerField()

    def __str__(self):
        return self.title


class Institution(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField(null=True, blank=True)
    country = models.ForeignKey(Country, null=True, on_delete=models.SET_NULL)

    def __str__(self):
        if self.country:
            return "%s (%s)" % (self.name, self.country.name)
        return self.name


class RatingChange(models.Model):
    profile = models.ForeignKey(
        "UserProfile", related_name="ratings", on_delete=models.CASCADE
    )
    contest = models.ForeignKey(
        Contest, related_name="rating_changes", on_delete=models.CASCADE
    )
    rating = models.IntegerField()
    seed = models.FloatField(default=0)
    rank = models.IntegerField()
    nick = models.CharField(max_length=20)

    @property
    def new_rating(self):
        return (
            RatingChange.objects.filter(
                profile=self.profile, contest__end_date__lte=self.contest.end_date
            )
            .aggregate(rating=Sum("rating"))
            .get("rating")
            + settings.BASE_RATING
        )

    @property
    def old_rating(self):
        return self.new_rating - self.rating


class Compiler(models.Model):
    language = models.CharField(max_length=20)
    name = models.CharField(max_length=50)
    arguments = models.CharField(max_length=1000)
    path = models.CharField(max_length=1000)
    file_extension = models.CharField(max_length=10, default="")
    exec_extension = models.CharField(max_length=10, default="")
    env = models.TextField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    @staticmethod
    def get_all_languages():
        return sorted(Compiler.objects.values_list("language", flat=True).distinct())


ROLE_CHOICES = [
    ("admin", "Administrator"),
    ("browser", "Code Browser"),
    ("observer", "Observer"),
    ("judge", "Judge"),
]

THEME_CHOICES = [
    ("hopscotch", "hopscotch"),
    ("ttcn", "ttcn"),
    ("ambiance-mobile", "ambiance-mobile"),
    ("paraiso-light", "paraiso-light"),
    ("icecoder", "icecoder"),
    ("zenburn", "zenburn"),
    ("erlang-dark", "erlang-dark"),
    ("seti", "seti"),
    ("midnight", "midnight"),
    ("tomorrow-night-bright", "tomorrow-night-bright"),
    ("panda-syntax", "panda-syntax"),
    ("bespin", "bespin"),
    ("ambiance", "ambiance"),
    ("neo", "neo"),
    ("solarized", "solarized"),
    ("base16-light", "base16-light"),
    ("vibrant-ink", "vibrant-ink"),
    ("abcdef", "abcdef"),
    ("yeti", "yeti"),
    ("mbo", "mbo"),
    ("xq-light", "xq-light"),
    ("twilight", "twilight"),
    ("rubyblue", "rubyblue"),
    ("base16-dark", "base16-dark"),
    ("neat", "neat"),
    ("dracula", "dracula"),
    ("cobalt", "cobalt"),
    ("lesser-dark", "lesser-dark"),
    ("3024-night", "3024-night"),
    ("pastel-on-dark", "pastel-on-dark"),
    ("liquibyte", "liquibyte"),
    ("colorforth", "colorforth"),
    ("blackboard", "blackboard"),
    ("monokai", "monokai"),
    ("xq-dark", "xq-dark"),
    ("elegant", "elegant"),
    ("3024-day", "3024-day"),
    ("night", "night"),
    ("mdn-like", "mdn-like"),
    ("tomorrow-night-eighties", "tomorrow-night-eighties"),
    ("isotope", "isotope"),
    ("material", "material"),
    ("eclipse", "eclipse"),
    ("paraiso-dark", "paraiso-dark"),
    ("railscasts", "railscasts"),
    ("the-matrix", "the-matrix"),
]


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, related_name="profile", primary_key=True, on_delete=models.CASCADE
    )
    role = models.CharField(max_length=10, null=True, blank=True, choices=ROLE_CHOICES)
    theme = models.CharField(
        max_length=25,
        null=True,
        choices=THEME_CHOICES,
        verbose_name=_("Code Editor Theme"),
    )
    avatar = models.ImageField(
        upload_to=UUIDImageName("user/avatar"),
        null=True,
        blank=True,
        verbose_name=_("Avatar"),
    )
    show_tags = models.BooleanField(default=True, verbose_name=_("Show tags"))
    institution = models.ForeignKey(
        Institution, null=True, verbose_name=_("Institution"), on_delete=models.SET_NULL
    )
    teams = models.ManyToManyField(Team, blank=True, related_name="profiles")
    rating_changes = models.ManyToManyField(Contest, through="RatingChange")
    compiler = models.ForeignKey(
        Compiler, null=True, verbose_name=_("Compiler"), on_delete=models.SET_NULL
    )
    points = models.PositiveIntegerField(
        verbose_name=_("Points"), null=False, default=0
    )
    email_notifications = models.BooleanField(
        verbose_name=_("Send email notifications"), default=True
    )

    def __init__(self, *args, **kwargs):
        super(UserProfile, self).__init__(*args, **kwargs)
        self.old_avatar_path = self.avatar.name

    def save(self, *args, **kwargs):
        super(UserProfile, self).save(*args, **kwargs)
        if self.old_avatar_path != self.avatar.name:
            try:
                if self.old_avatar_path:
                    os.remove(os.path.join(settings.MEDIA_ROOT, self.old_avatar_path))
            except:
                pass
            try:
                from PIL import Image

                img = Image.open(self.avatar.path)
                img.thumbnail((300, 300))
                img.save(self.avatar.path)
            except:
                pass

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_observer(self):
        return self.role == "observer"

    @property
    def is_judge(self):
        return self.role == "judge"

    @property
    def is_browser(self):
        return self.role == "browser"

    @property
    def rating(self):
        if self.has_rating:
            return (
                RatingChange.objects.filter(profile=self)
                .aggregate(rating=Sum("rating"))
                .get("rating")
                + settings.BASE_RATING
            )
        else:
            return 0

    @property
    def has_rating(self):
        return self.rating_changes.count() > 0

    def get_ratings(self):
        data = []
        cumul = settings.BASE_RATING
        for rc in (
            self.ratings.all().select_related("contest").order_by("contest__start_date")
        ):
            cumul += rc.rating
            data.append(
                {
                    "date": rc.contest.start_date.__format__("%Y-%m-%d"),
                    "name": rc.contest.name,
                    "url": reverse(
                        "mog:contest_problems", kwargs={"contest_id": rc.contest_id}
                    ),
                    "rank": rc.rank,
                    "rating": cumul,
                    "change": rc.rating,
                }
            )
        return data

    @property
    def solved_problems(self):
        return (
            self.user.submissions.filter(
                result__name__iexact="accepted", hidden=False, status="normal"
            )
            .distinct("problem_id")
            .count()
        )

    @property
    def accepted_submissions(self):
        return self.user.submissions.filter(
            result__name__iexact="accepted", hidden=False, status="normal"
        ).count()

    @property
    def total_submissions(self):
        return self.user.submissions.filter(hidden=False).count()

    @staticmethod
    def sorted_by_ratings():
        return (
            UserProfile.objects.annotate(
                rating_value=Coalesce(
                    Sum("ratings__rating"), Value(-settings.BASE_RATING)
                )
            )
            .order_by("-rating_value", "-points", "pk")
            .select_related("user")
        )

    def __str__(self):
        return self.user.username


class Result(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=250, null=True)
    color = models.CharField(max_length=50)
    penalty = models.BooleanField()

    @staticmethod
    def get_all_results():
        return Result.objects.all()

    def __str__(self):
        return self.name


class Submission(models.Model):
    STATUS_CHOICES = [("normal", "normal"), ("frozen", "frozen"), ("death", "death")]

    problem = models.ForeignKey(
        Problem, related_name="submissions", on_delete=models.CASCADE
    )
    instance = models.ForeignKey(
        "ContestInstance",
        null=True,
        blank=True,
        related_name="submissions",
        on_delete=models.SET_NULL,
    )
    date = models.DateTimeField()
    execution_time = models.IntegerField(default=0)
    memory_used = models.BigIntegerField(default=0)
    source = models.TextField()
    user = models.ForeignKey(User, related_name="submissions", on_delete=models.CASCADE)
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    compiler = models.ForeignKey(Compiler, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    judgement_details = models.TextField(null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="normal")

    @property
    def visible(self):
        return not self.hidden and (
            self.instance is None or self.instance.contest.visible
        )

    def can_be_rejudged_by(self, user):
        return user_is_admin(user) or user_is_judge_in_contest(
            user, self.problem.contest
        )

    def can_show_judgment_details_to(self, user):
        """Determine whether an user can see judgment details of the submission.
        An user can see judgment details only if:
        - The user is an administrator, or the submission is visible and the user
        is observer or
        - does not belong to a running instance and the submission.status='normal' and (is visible and public...
        or belongs to the user)
        """
        if (
            user_is_admin(user)
            or user_is_judge_in_contest(user, self.problem.contest)
            or (
                self.visible and user_is_observer_in_contest(user, self.problem.contest)
            )
        ):
            return True

        if not self.instance or self.instance.is_past:
            return self.status == "normal" and (
                (user.is_authenticated and self.user == user)
                or (self.visible and self.public)
            )
        return False

    def can_show_details_to(self, user):
        """Determine whether an user can see details of the submission
        (result, time, memory, etc) or not. An user can see details only
        if:
         - The user is an administrator, or the submission is visible and the user
        is observer or
        - The submission is visible and the status is 'normal'
        - The submission belongs to the user and is not death
        """
        if (
            user_is_admin(user)
            or user_is_judge_in_contest(user, self.problem.contest)
            or (
                self.visible and user_is_observer_in_contest(user, self.problem.contest)
            )
        ):
            return True

        if self.status == "normal" and self.visible:
            return True

        return user.is_authenticated and self.user == user and self.status != "death"

    def can_show_source_to(self, user):
        """Determine whether the user has the permissions to see the
        current submission's source code. An user can see the source
        code only if:
        - User is the author of the submission, or
        - User is an administrator, or
        - User is judge in the contest where the submission was sent, or
        - User is observer in the contest and the submission is visible, or
        - The submission is visible and public and does not belong to a
        running instance (allow no-logged users).
        """
        if self.user == user:
            return True
        if user_is_admin(user):
            return True
        if user_is_judge_in_contest(user, self.problem.contest):
            return True
        if self.visible and user_is_observer_in_contest(user, self.problem.contest):
            return True
        if (
            self.visible
            and self.public
            and (not self.instance or self.instance.is_past)
        ):
            return True
        return False

    def __str__(self):
        return str(self.id)

    @property
    def is_accepted(self):
        return self.result.name == "Accepted"

    @property
    def is_pending(self):
        return self.result.name == "Pending"

    @property
    def is_normal(self):
        return self.status == "normal"

    @property
    def is_frozen(self):
        return self.status == "frozen"

    @property
    def is_death(self):
        return self.status == "death"


class Comment(models.Model):
    user = models.ForeignKey(User, related_name="comments", on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name="comments", on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    body = models.TextField()
    html = models.TextField(default="")
    seen = models.ManyToManyField(User, related_name="seen_comments")

    def __init__(self, *args, **kwargs):
        super(Comment, self).__init__(*args, **kwargs)
        self.initial_body_value = self.body

    def save(self, *args, **kwargs):
        if not self.pk or (self.initial_body_value != self.body):
            matches = map(
                lambda match: (match.start(), match.end()),
                list(re.finditer("@[\S]+", self.body, re.S)),
            )
            self.html = ""
            last_index, users = 0, set()
            for s, e in matches:
                if not last_index:
                    self.html = cgi.escape(self.body[:s], quote=True)
                username = self.body[(s + 1) : e]
                try:
                    user = User.objects.get(username=username)
                    users.add(user)
                    url = render_to_string(
                        "mog/user/_link.html", {"user": user}
                    ).strip()
                    self.html += " " + url
                except:
                    self.html += cgi.escape(self.body[s:e], quote=True)
                last_index = e
            self.html += cgi.escape(self.body[last_index:], quote=True)
            # notify users about this comment
            for user in users:
                send_mail(
                    "{0} has mentioned you in a comment".format(self.user.username),
                    message="<NO TEXT>",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                    html_message=render_to_string(
                        "mog/email/mention.html",
                        {
                            "user": self.user,
                            "comment": self,
                            "domain": "http://matcomgrader.com",
                        },
                    ),
                )
        # save now
        super(Comment, self).save(*args, **kwargs)

    def can_be_edited_by(self, user):
        return user_is_admin(user)

    def can_be_removed_by(self, user):
        return user_is_admin(user)


class ContestInstance(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, related_name="instances", on_delete=models.CASCADE
    )
    team = models.ForeignKey(
        Team, null=True, blank=True, related_name="instances", on_delete=models.CASCADE
    )
    contest = models.ForeignKey(
        Contest, related_name="instances", on_delete=models.CASCADE
    )
    start_date = models.DateTimeField(null=True, blank=True)
    real = models.BooleanField()
    group = models.CharField(
        max_length=64, null=True, blank=True, verbose_name=_("Group name")
    )
    render_team_description_only = models.BooleanField(
        default=False,
        verbose_name=_(
            "If true, render the team without members and only displaying the description on hover"
        ),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_(
            "If true, it will allows the instance to submit to the corresponding contest."
        ),
    )

    def __str__(self):
        if self.team:
            return "Team: " + self.team.name
        return self.user.username

    @property
    def institution(self):
        if self.team:
            return self.team.institution
        if self.user:
            return self.user.profile.institution
        return None

    @property
    def instance_start_date(self):
        if self.real:
            return self.contest.start_date
        return self.start_date

    @property
    def end_date(self):
        if self.real:
            return self.contest.end_date
        return self.start_date + self.contest.duration

    @property
    def relative_time(self):
        if self.real:
            return timezone.now() - self.contest.start_date
        return timezone.now() - self.start_date

    @property
    def remaining_time(self):
        if self.real:
            return self.contest.end_date - timezone.now()
        return self.contest.duration - (timezone.now() - self.start_date)

    @property
    def percent(self):
        if self.real:
            return self.contest.percent
        return (
            (timezone.now() - self.start_date).total_seconds()
            * 100
            // self.contest.duration.total_seconds()
        )

    @property
    def is_coming(self):
        if self.real:
            return self.contest.is_coming
        # A virtual instance is never coming
        return False

    @property
    def is_past(self):
        if self.real:
            return self.contest.is_past
        return timezone.now() > self.start_date + self.contest.duration

    def is_running_at(self, timestamp):
        if self.real:
            return self.contest.is_running_at(timestamp)
        return self.start_date <= timestamp <= self.start_date + self.contest.duration

    @property
    def is_running(self):
        return self.is_running_at(timezone.now())

    @property
    def is_frozen_time(self):
        end_date = self.end_date
        return (
            end_date - timezone.timedelta(minutes=self.frozen_time)
            < timezone.now()
            < end_date
        )

    @property
    def is_death_time(self):
        end_date = self.end_date
        return (
            end_date - timezone.timedelta(minutes=self.death_time)
            < timezone.now()
            < end_date
        )

    @property
    def frozen_time(self):
        if self.real:
            return self.contest.frozen_time
        return 0

    @property
    def death_time(self):
        if self.real:
            return self.contest.death_time
        return 0

    def submissions_for_problem(self, problem):
        return self.submissions.filter(problem=problem)

    def has_solved_problem(self, problem):
        return (
            self.submissions_for_problem(problem)
            .filter(result__name__iexact="accepted", status="normal")
            .count()
            > 0
        )

    def has_failed_problem(self, problem):
        return (
            self.submissions_for_problem(problem)
            .filter(result__penalty=True, status="normal")
            .count()
            > 0
        )


class Clarification(models.Model):
    contest = models.ForeignKey(
        Contest,
        on_delete=models.CASCADE,
        related_name="clarifications",
        verbose_name=_("Contest"),
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.SET_NULL,
        related_name="clarifications",
        blank=True,
        null=True,
        verbose_name=_("Problem"),
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clarifications",
        null=True,
    )
    fixer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        default=None,
        null=True,
    )
    seen = models.ManyToManyField(User, related_name="seen_clarifications")
    public = models.BooleanField(default=False, verbose_name=_("Public"))
    question = models.CharField(max_length=2048, verbose_name=_("Question"))
    answer = models.TextField(blank=True, null=True, verbose_name=_("Answer"))
    asked_date = models.DateTimeField(auto_now_add=True)
    answered_date = models.DateTimeField(null=True)

    def save(self, *args, **kwargs):
        new_instance = self.pk is None
        super(Clarification, self).save(*args, **kwargs)
        if new_instance:
            report_clarification(clarification=self)

    def formset(self):
        from mog.forms import ClarificationExtendedForm

        return ClarificationExtendedForm(instance=self)


class UserFeedback(models.Model):
    STATUS_CHOICES = [
        ("open", "OPEN"),
        ("in_progress", "IN_PROGRESS"),
        ("closed", "CLOSED"),
    ]
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedbacks")
    submitted_date = models.DateTimeField(auto_now_add=True)
    subject = models.CharField(max_length=1024, verbose_name=_("Subject"))
    description = models.TextField(blank=True, null=True, verbose_name=_("Description"))
    screenshot = models.ImageField(
        upload_to=UUIDImageName("screenshot"),
        null=True,
        blank=True,
        verbose_name=_("Screenshot"),
    )
    status = models.CharField(max_length=20, default="open", choices=STATUS_CHOICES)
    assigned = models.ForeignKey(
        User,
        null=True,
        blank=True,
        related_name="assigned_feedbacks",
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return self.subject


class ContestPermission(models.Model):
    CONTEST_ROLE_CHOICES = [
        ("judge", "Judge"),
        ("observer", "Observer"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=16, null=True, blank=True, choices=CONTEST_ROLE_CHOICES
    )
    granted = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
