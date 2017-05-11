from __future__ import unicode_literals

import os

from django.db.models import F, Max
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce

from django.contrib.auth.models import User
from django.db import models
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import ugettext_lazy as _

from mog.utils import user_is_admin, user_is_browser


class Team(models.Model):
    name = models.CharField(max_length=100)
    institution = models.ForeignKey('Institution', null=True, blank=True)
    description = models.CharField(max_length=250, null=True)

    def __unicode__(self):
        return '{0} ({1})'.format(
            self.name,
            ', '.join([profile.user.username for profile in self.profiles.all()])
        )


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=250, null=True)

    def get_visible_problems(self, admin=False):
        return self.problems if admin else self.problems.filter(contest__visible=True)

    def __unicode__(self):
        return self.name


class Checker(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    source = models.TextField()

    def __unicode__(self):
        return self.name


class Contest(models.Model):
    name = models.CharField(max_length=100, unique=False)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    visible = models.BooleanField(default=False)
    frozen_time = models.IntegerField(verbose_name="Frozen time (minutes)", default=0)
    death_time = models.IntegerField(verbose_name="Death time (minutes)", default=0)
    closed = models.BooleanField(verbose_name="Closed registration", default=False)
    allow_teams = models.BooleanField(verbose_name="Allow teams", default=False)
    rated = models.BooleanField(default=False)

    def __unicode__(self):
        return self.name

    def can_be_seen_by(self, user):
        """
        > problems
        > standings
        > submissions
        > submit
        """
        return user_is_admin(user) or (self.visible and not self.is_coming)

    @property
    def relative_time(self):
        return timezone.now() - self.start_date

    @property
    def remaining_time(self):
        return self.duration - self.relative_time

    @property
    def percent(self):
        return (timezone.now() - self.start_date).total_seconds() * 100 / self.duration.total_seconds()

    @property
    def duration(self):
        return self.end_date - self.start_date

    @property
    def is_coming(self):
        return timezone.now() < self.start_date

    @property
    def is_past(self):
        return self.end_date < timezone.now()

    @property
    def is_running(self):
        return self.visible and self.start_date <= timezone.now() <= self.end_date

    def real_registration(self, user):
        """Return the real instance related with this contest and a given user"""
        if not user.is_authenticated():
            return None
        return self.instances.filter(Q(real=True) & (Q(user=user) | Q(team__in=user.profile.teams.all()))).first()

    def virtual_registration(self, user):
        """Return the virtual instance related with this contest and a given user"""
        if not user.is_authenticated():
            return None
        return self.instances.filter(Q(real=False) & (Q(user=user) | Q(team__in=user.profile.teams.all()))).first()

    def registered_for_real(self, user):
        return self.real_registration(user) is not None

    def registered_for_virtual(self, user):
        return self.virtual_registration(user) is not None

    def can_register_for_real(self, user):
        """
        User can register in contest for real
        competition if the following five conditions
        hold:
        1) User is authenticated
        2) Contest is coming.
        3) Contest is open for registration.
        4) User is not admin neither code browser.
        5) User is not registered (individually or in a team).
        """
        if not user.is_authenticated() or not self.is_coming or self.closed:
            return False
        if user_is_admin(user) or user_is_browser(user):
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
        1) User is authenticated.
        2) Contest is already finished.
        3) User is not admin neither code browser.
        4) User is not registered (individually or in a team).
        """
        if not user.is_authenticated() or not self.is_past:
            return False
        if user_is_admin(user) or user_is_browser(user):
            return False
        return not self.registered_for_virtual(user)

    def virtual_percent(self, user):
        raise NotImplementedError()

    @property
    def get_problems(self):
        return self.problems.order_by('position')

    @property
    def is_death_time(self):
        return self.end_date - timezone.timedelta(minutes=self.death_time) <= timezone.now() <= self.end_date

    @property
    def is_frozen_time(self):
        return self.end_date - timezone.timedelta(minutes=self.frozen_time) <= timezone.now() <= self.end_date

    @staticmethod
    def get_visible_contests(admin=False):
        return Contest.objects if admin else Contest.objects.filter(visible=True)

    @staticmethod
    def get_all_contests(admin=False):
        now = timezone.now()
        contests = Contest.get_visible_contests(admin)
        running = contests.filter(start_date__lte=now, end_date__gte=now).order_by('start_date')
        coming = contests.filter(start_date__gt=now).order_by('start_date')
        past = contests.filter(end_date__lt=now).order_by('-start_date')
        return running, coming, past


class Problem(models.Model):
    title = models.CharField(max_length=100)
    body = models.TextField(blank=True)
    input = models.TextField(blank=True)
    output = models.TextField(blank=True)
    hints = models.TextField(null=True, blank=True)
    time_limit = models.PositiveIntegerField(verbose_name='Time limit (s)')
    memory_limit = models.PositiveIntegerField(verbose_name='Memory limit (MB)')
    tags = models.ManyToManyField(Tag, related_name='problems', blank=True)
    checker = models.ForeignKey(Checker, null=True)
    position = models.IntegerField()
    points = models.IntegerField()
    balloon = models.CharField(verbose_name="Balloon color", max_length=50)
    contest = models.ForeignKey(Contest, related_name='problems')
    slug = models.SlugField(max_length=100, null=True)
    compilers = models.ManyToManyField('Compiler')

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super(Problem, self).save(*args, **kwargs)

    def _visible_submissions(self):
        return self.submissions. \
            filter(Q(hidden=False) & (Q(instance=None) | Q(instance__contest__visible=True)))

    def _accepted_submissions(self):
        return self._visible_submissions().filter(result__name__iexact='accepted')

    @staticmethod
    def get_visible_problems(admin=False):
        return Problem.objects if admin else Problem.objects.filter(contest__visible=True)

    @property
    def letter(self):
        if self.position < 1 or self.position > 26:
            return '?'
        return chr(ord('A') + self.position - 1)

    @property
    def code(self):
        return self.contest.code + self.letter

    @property
    def full_title(self):
        return self.letter + ' - ' + self.title

    @property
    def user_submitted(self):
        """Number of users that have at least one submission to this problem"""
        return self._visible_submissions().distinct('user_id').count()

    @property
    def accepted_submissions(self):
        """Number of accepted submissions"""
        return self._accepted_submissions().count()

    @property
    def total_submissions(self):
        """Total number of submissions"""
        return self._visible_submissions().count()

    @property
    def solved(self):
        """Return number of contestant whom solved this problem"""
        return self._accepted_submissions().distinct('user_id').count()

    @property
    def solved_in_real(self):
        """Return number of contestants whom solved this problem in a real contest"""
        return self._accepted_submissions().filter(instance__real=True).distinct('user_id').count()

    """
    @property
    def points(self):
        return 108 / (12 + self.solved) + 1
    """

    @property
    def compilers_by_relevance(self):
        def relevance(compiler):
            name = compiler.language.lower()
            if name == 'csharp': return 0
            if name == 'cpp': return 1
            if name == 'python': return 2
            if name == 'java': return 3
            return 4
        return sorted(self.compilers.all(), key=relevance)

    @property
    def first_compilers(self):
        return ','.join([compiler.name for compiler in self.compilers_by_relevance[:2]])

    @property
    def compilers2str(self):
        return '<br>'.join([compiler.language for compiler in self.compilers_by_relevance])

    def __unicode__(self):
        return self.title


class Post(models.Model):
    name = models.CharField(max_length=250)
    body = models.TextField(blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    modification_date = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User)
    show_in_main_page = models.BooleanField(default=False)
    slug = models.SlugField(max_length=250, null=True)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super(Post, self).save(*args, **kwargs)

    def can_be_edited_by(self, user, admin=False):
        return admin or self.user == user

    def unseen_comments(self, user):
        return Comment.objects.filter(Q(post=self), ~Q(pk__in=user.seen_comments.all())).count()

    def update_seen_comments(self, user):
        unseen_comments = Comment.objects.filter(Q(post=self), ~Q(pk__in=user.seen_comments.all()))
        for comment in unseen_comments.all():
            comment.seen.add(user)

    @property
    def sorted_comments(self):
        return self.comments.order_by('-date').all()

    def __unicode__(self):
        return self.name


class Message(models.Model):
    source = models.ForeignKey(User, related_name='messages_sent')
    target = models.ForeignKey(User, related_name='messages_received')
    subject = models.CharField(max_length=250)
    body = models.TextField()
    date = models.DateTimeField(auto_now=True)
    saw = models.BooleanField(default=False)


class Division(models.Model):
    title = models.CharField(max_length=50)
    color = models.CharField(max_length=50)
    rating = models.PositiveIntegerField()

    def __unicode__(self):
        return self.title


class Institution(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField()
    country = models.CharField(max_length=50)

    def __unicode__(self):
        return '{0} ({1})'.format(self.name, self.country)


class RatingChange(models.Model):
    profile = models.ForeignKey('UserProfile', related_name='ratings')
    contest = models.ForeignKey(Contest, related_name='rating_changes')
    rating = models.IntegerField()
    rank = models.IntegerField()
    nick = models.CharField(max_length=20)


class Compiler(models.Model):
    language = models.CharField(max_length=20)
    name = models.CharField(max_length=50)
    arguments = models.CharField(max_length=1000)
    path = models.CharField(max_length=1000)
    file_extension = models.CharField(max_length=10, default='')
    exec_extension = models.CharField(max_length=10, default='')

    def __unicode__(self):
        return '[{0}] {1}'.format(self.language, self.name)

    @staticmethod
    def get_all_compilers():
        return Compiler.objects.all()


ROLE_CHOICES = [
    ('admin', 'Administrator'),
    ('browser', 'Code Browser'),
]

THEME_CHOICES = [('hopscotch', 'hopscotch'), ('ttcn', 'ttcn'), ('ambiance-mobile', 'ambiance-mobile'),
                 ('paraiso-light', 'paraiso-light'), ('icecoder', 'icecoder'), ('zenburn', 'zenburn'),
                 ('erlang-dark', 'erlang-dark'), ('seti', 'seti'), ('midnight', 'midnight'),
                 ('tomorrow-night-bright', 'tomorrow-night-bright'), ('panda-syntax', 'panda-syntax'),
                 ('bespin', 'bespin'), ('ambiance', 'ambiance'), ('neo', 'neo'), ('solarized', 'solarized'),
                 ('base16-light', 'base16-light'), ('vibrant-ink', 'vibrant-ink'), ('abcdef', 'abcdef'),
                 ('yeti', 'yeti'), ('mbo', 'mbo'), ('xq-light', 'xq-light'), ('twilight', 'twilight'),
                 ('rubyblue', 'rubyblue'), ('base16-dark', 'base16-dark'), ('neat', 'neat'),
                 ('dracula', 'dracula'), ('cobalt', 'cobalt'), ('lesser-dark', 'lesser-dark'),
                 ('3024-night', '3024-night'), ('pastel-on-dark', 'pastel-on-dark'), ('liquibyte', 'liquibyte'),
                 ('colorforth', 'colorforth'), ('blackboard', 'blackboard'), ('monokai', 'monokai'),
                 ('xq-dark', 'xq-dark'), ('elegant', 'elegant'), ('3024-day', '3024-day'), ('night', 'night'),
                 ('mdn-like', 'mdn-like'), ('tomorrow-night-eighties', 'tomorrow-night-eighties'),
                 ('isotope', 'isotope'), ('material', 'material'), ('eclipse', 'eclipse'),
                 ('paraiso-dark', 'paraiso-dark'), ('railscasts', 'railscasts'), ('the-matrix', 'the-matrix')]


class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name='profile', primary_key=True)
    role = models.CharField(max_length=10, null=True, blank=True, choices=ROLE_CHOICES)
    theme = models.CharField(max_length=20, null=True, choices=THEME_CHOICES, verbose_name=_('Code Editor Theme'))
    avatar = models.ImageField(upload_to='user/avatar', null=True, blank=True, verbose_name=_('Avatar'))
    show_tags = models.BooleanField(default=True, verbose_name=_('Show tags'))
    institution = models.ForeignKey(Institution, null=True, verbose_name=_('Institution'))
    teams = models.ManyToManyField(Team, blank=True, related_name='profiles')
    rating_changes = models.ManyToManyField(Contest, through='RatingChange')
    compiler = models.ForeignKey(Compiler, null=True, verbose_name=_('Compiler'))

    def __init__(self, *args, **kwargs):
        super(UserProfile, self).__init__(*args, **kwargs)
        self.old_avatar_path = self.avatar.name

    def save(self, *args, **kwargs):
        super(UserProfile, self).save(*args, **kwargs)
        if self.old_avatar_path != self.avatar.name:
            try:
                os.remove(os.path.join(settings.MEDIA_ROOT, self.old_avatar_path))
                from PIL import Image
                img = Image.open(self.avatar.path)
                img.thumbnail((300, 300))
                img.save(self.avatar.path)
            except Exception, e:
                pass

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_browser(self):
        return self.role == 'browser'

    @property
    def rating(self):
        return RatingChange.objects.filter(profile=self)\
            .aggregate(rating=Sum('rating')).get('rating') or 0

    def get_ratings(self):
        data = []
        cumul = 0
        for rc in self.ratings.all().select_related('contest').order_by('contest__start_date'):
            cumul += rc.rating
            data.append(
                {
                    'date': rc.contest.start_date.__format__('%Y-%m-%d'),
                    'name': rc.contest.name,
                    'url': reverse('mog:contest_problems', kwargs={'contest_id': rc.contest_id}),
                    'rank': rc.rank, 'rating': cumul, 'change': rc.rating
                }
            )
        return data

    @property
    def points(self):
        return self.user.submissions.filter(result__name__iexact='accepted', hidden=False)\
            .values('problem_id').annotate(pnts=Max('problem__points')).aggregate(result=Sum('pnts'))['result']

    @property
    def solved_problems(self):
        return self.user.submissions.filter(result__name__iexact='accepted', hidden=False)\
            .distinct('problem_id').count()

    @property
    def accepted_submissions(self):
        return self.user.submissions.filter(hidden=False, result__name__iexact='accepted').count()

    @property
    def total_submissions(self):
        return self.user.submissions.filter(hidden=False).count()

    @staticmethod
    def sorted_by_ratings():
        return UserProfile.objects.annotate(rating_value=Coalesce(Sum('ratings__rating'), Value(0))). \
            order_by('-rating_value').select_related('user')

    def __unicode__(self):
        return self.user.username


class Result(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=250, null=True)
    color = models.CharField(max_length=50)
    penalty = models.BooleanField()

    @staticmethod
    def get_all_results():
        return Result.objects.all()

    def __unicode__(self):
        return self.name


class Submission(models.Model):
    problem = models.ForeignKey(Problem, related_name='submissions')
    instance = models.ForeignKey('ContestInstance', null=True, blank=True, related_name='submissions')
    date = models.DateTimeField(auto_now_add=True)
    execution_time = models.IntegerField(default=0)
    memory_used = models.IntegerField(default=0)
    source = models.TextField()
    user = models.ForeignKey(User, related_name='submissions')
    result = models.ForeignKey(Result)
    compiler = models.ForeignKey(Compiler)
    public = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    judgement_details = models.TextField(null=True)

    def can_show_judgment_details_to(self, user):
        if user_is_admin(user) or not self.instance \
                or not self.instance.real or self.instance.is_past:
            return True
        s, e = self.instance.end_date - timezone.timedelta(minutes=self.instance.death_time),\
               self.instance.end_date
        if self.instance.is_death_time and s < self.date < e:
            return False
        s, e = self.instance.end_date - timezone.timedelta(minutes=self.instance.frozen_time), \
               self.instance.end_date
        if self.instance.is_frozen_time and s < self.date < e:
            return self.user == user
        return False

    def can_show_details_to(self, user):
        if user_is_admin(user) or not self.instance \
                or not self.instance.real or self.instance.is_past:
            return True
        s, e = self.instance.end_date - timezone.timedelta(minutes=self.instance.death_time),\
               self.instance.end_date
        if self.instance.is_death_time and s < self.date < e:
            return False
        s, e = self.instance.end_date - timezone.timedelta(minutes=self.instance.frozen_time), \
               self.instance.end_date
        if self.instance.is_frozen_time and s < self.date < e:
            return self.user == user
        return True

    @property
    def visible(self):
        return not self.hidden and (self.instance is None or self.instance.contest.visible)

    def can_show_source_to(self, user):
        if not user.is_authenticated():
            return False
        if self.user == user:
            return True
        profile = user.profile if hasattr(user, 'profile') else None
        if profile:
            return profile.is_admin or (profile.is_browser and self.visible)

    @staticmethod
    def visible_submissions(user):
        """Submissions to show in submission list"""
        if user_is_admin(user):
            return Submission.objects
        return Submission.objects \
            .filter(Q(hidden=False) & (Q(instance=None) | Q(instance__contest__visible=True)))

    def __unicode__(self):
        return str(self.id)


class Comment(models.Model):
    user = models.ForeignKey(User, related_name='comments')
    post = models.ForeignKey(Post, related_name='comments')
    date = models.DateTimeField(auto_now_add=True)
    body = models.TextField()
    seen = models.ManyToManyField(User, related_name='seen_comments')

    def can_be_edited_by(self, user):
        return user_is_admin(user)


class ContestInstance(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, related_name='instances')
    team = models.ForeignKey(Team, null=True, blank=True, related_name='instances')
    contest = models.ForeignKey(Contest, related_name='instances')
    start_date = models.DateTimeField(null=True, blank=True)
    real = models.BooleanField()

    def __unicode__(self):
        if self.team:
            return 'Team: ' + self.team.name
        return self.user.username

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
        return (timezone.now() - self.start_date).total_seconds() * 100 / self.contest.duration.total_seconds()

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

    @property
    def is_running(self):
        if self.real:
            return self.contest.is_running
        return self.start_date <= timezone.now() <= self.start_date + self.contest.duration

    @property
    def is_frozen_time(self):
        end_date = self.end_date
        return end_date - timezone.timedelta(minutes=self.frozen_time) < timezone.now() < end_date

    @property
    def is_death_time(self):
        end_date = self.end_date
        return end_date - timezone.timedelta(minutes=self.death_time) < timezone.now() < end_date

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

    def get_submissions(self, problem, instance_bound=None):
        submissions = self.submissions.filter(problem=problem)
        if instance_bound:
            submissions = submissions\
                .filter(
                    (Q(instance__real=True) & Q(instance__contest__start_date__gte=(F('date') - instance_bound.relative_time)))
                    | (Q(instance__real=False) & Q(instance__start_date__gte=(F('date') - instance_bound.relative_time)))
                )
        return submissions
