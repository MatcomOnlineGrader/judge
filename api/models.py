import os
import re
import cgi
import uuid

from django.core.mail import send_mail
from django.db.models import F
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce, Lower

from django.template.loader import render_to_string

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
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
from mog.utils import user_is_admin, user_is_browser, user_is_observer


@deconstructible
class UUIDImageName(object):
    def __init__(self, upload_to):
        self.upload_to = upload_to

    def __call__(self, instance, filename):
        extension = '.' + filename.split('.')[-1].lower()
        if extension not in ['.jpg', '.jpeg', '.png', '.gif']:
            extension = '.png'
        return os.path.join(self.upload_to, '%s%s' % (str(uuid.uuid4()), extension))


class Country(models.Model):
    class Meta:
        verbose_name_plural = 'Countries'

    name = models.CharField(verbose_name='Country Name', max_length=64)
    flag = models.CharField(verbose_name='Country Flag URL', max_length=128)

    def __str__(self):
        return self.name

    def flag_image_tag(self):
        return mark_safe('<img src="%s" alt="%s">' % (self.flag, self.name))

    flag_image_tag.short_description = 'Flag Image'


class Team(models.Model):
    name = models.CharField(max_length=100)
    institution = models.ForeignKey(
        'Institution',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    description = models.TextField(null=True)
    icpcid = models.CharField(max_length=64, null=True, blank=True,
        verbose_name=_('ID that links this team to the ICPC, we get this value down from baylor'))

    def __str__(self):
        return '{0} ({1})'.format(
            self.name,
            ', '.join([profile.user.username for profile in self.profiles.all()])
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
        ('testlib.h', 'testlib.h'),
        ('testlib4j.jar', 'testlib4j.jar')
    ]

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    source = models.TextField()
    backend = models.CharField(max_length=32, choices=BACKEND_CHOICES, default='testlib.h')

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
    group = models.CharField(max_length=64, blank=True, null=True, verbose_name=_('Default group'))

    def __str__(self):
        return self.name

    def can_be_seen_by(self, user):
        """
        > problems
        > standings
        > submissions
        > submit
        """
        return user_is_admin(user) or (self.visible and not self.is_coming)

    def can_show_saris_to(self, user):
        return user_is_admin(user) or (self.visible and user_is_observer(user))

    @property
    def relative_time(self):
        return timezone.now() - self.start_date

    @property
    def remaining_time(self):
        return self.duration - self.relative_time

    @property
    def percent(self):
        return (timezone.now() - self.start_date).total_seconds() * 100 // self.duration.total_seconds()

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
        return self.instances.filter(Q(real=True) & (Q(user=user) | Q(team__in=user.profile.teams.all()))).first()

    def virtual_registration(self, user):
        """Return the virtual instance related with this contest and a given user"""
        if not user.is_authenticated:
            return None
        return self.instances.filter(Q(real=False) & (Q(user=user) | Q(team__in=user.profile.teams.all()))).first()

    def registration(self, user):
        return self.real_registration(user) or self.virtual_registration(user)

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
        2) Contest is coming or running.
        3) Contest is open for registration.
        4) User is not admin neither code browser.
        5) User is not registered (individually or in a team).
        """
        if not user.is_authenticated or self.is_past or self.closed:
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
        2) Contest is already finished and unfrozen.
        3) User is not admin neither code browser.
        4) User is not registered (individually or in a team).
        """
        if not user.is_authenticated or not self.is_past or self.needs_unfreeze:
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

    def visible_clarifications(self, user):
        if user_is_admin(user):
            return self.clarifications.order_by('-asked_date')
        if user.is_authenticated:
            return self.clarifications.filter(Q(public=True) | Q(sender=user))\
                .order_by('-asked_date')
        return self.clarifications.filter(public=True)\
            .order_by('-asked_date')

    def unseen_clarifications(self, user):
        if user.is_authenticated:
            clarifications = self.clarifications if user_is_admin(user) else\
                self.clarifications.filter(Q(public=True) | Q(sender=user))
            return clarifications.filter(~Q(pk__in=user.seen_clarifications.all())).count()

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

    def group_names(self):
        return list(
            self.instances.order_by(Lower('group'))\
                .values_list('group', flat=True).distinct()
        )


class Problem(models.Model):
    LETTER_COLOR_CHOICES = [
        ('#ffffff', 'white'),
        ('#000000', 'black')
    ]
    title = models.CharField(max_length=100)
    body = models.TextField(blank=True)
    input = models.TextField(blank=True)
    output = models.TextField(blank=True)
    hints = models.TextField(null=True, blank=True)
    time_limit = models.PositiveIntegerField(verbose_name='Time limit (s)')
    memory_limit = models.PositiveIntegerField(verbose_name='Memory limit (MB)')
    tags = models.ManyToManyField(Tag, related_name='problems', blank=True)
    checker = models.ForeignKey(Checker, null=True, on_delete=models.SET_NULL)
    position = models.IntegerField()
    points = models.IntegerField(default=10)
    balloon = models.CharField(verbose_name="Balloon color", max_length=50, null=True, blank=True)
    letter_color = models.CharField(max_length=20, choices=LETTER_COLOR_CHOICES, default='#ffffff')
    contest = models.ForeignKey(Contest, related_name='problems', on_delete=models.CASCADE)
    slug = models.SlugField(max_length=100, null=True)
    compilers = models.ManyToManyField('Compiler')

    def save(self, *args, **kwargs):
        self.slug = slugify(self.title)
        super(Problem, self).save(*args, **kwargs)

    def _visible_submissions(self):
        return self.submissions. \
            filter(Q(hidden=False) & (Q(instance=None) | Q(instance__contest__visible=True)))

    def _accepted_submissions(self):
        return self._visible_submissions().filter(result__name__iexact='accepted', status='normal')

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
            return {
                'csharp': 0,
                'cpp': 1,
                'python': 2,
                'java': 3
            }.get(compiler.language.lower(), 4)
        return sorted(self.compilers.all(), key=relevance)

    @property
    def first_compilers(self):
        return ','.join([compiler.name for compiler in self.compilers_by_relevance[:2]])

    @property
    def compilers2str(self):
        return '<br>'.join([compiler.name for compiler in self.compilers_by_relevance])

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
        return Comment.objects.filter(Q(post=self), ~Q(pk__in=user.seen_comments.all())).count()

    def update_seen_comments(self, user):
        unseen_comments = Comment.objects.filter(Q(post=self), ~Q(pk__in=user.seen_comments.all()))
        for comment in unseen_comments.all():
            comment.seen.add(user)

    def can_be_commented_by(self, user):
        """
        A user can comment on a post if the user is active and has some
        problem accepted (the number of points should be positive).
        """
        return user.is_authenticated and user.is_active and \
            hasattr(user, 'profile') and user.profile.points > 0

    @property
    def sorted_comments(self):
        return self.comments.order_by('-date').all()

    def __str__(self):
        return self.name


class Message(models.Model):
    source = models.ForeignKey(User, related_name='messages_sent', on_delete=models.CASCADE)
    target = models.ForeignKey(User, related_name='messages_received', on_delete=models.CASCADE)
    subject = models.CharField(max_length=250)
    body = models.TextField()
    date = models.DateTimeField(auto_now=True)
    saw = models.BooleanField(default=False)


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
            return '%s (%s)' % (self.name, self.country.name)
        return self.name


class RatingChange(models.Model):
    profile = models.ForeignKey('UserProfile', related_name='ratings', on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, related_name='rating_changes', on_delete=models.CASCADE)
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

    def __str__(self):
        return self.name

    @staticmethod
    def get_all_compilers():
        return Compiler.objects.order_by('name').all()


ROLE_CHOICES = [
    ('admin', 'Administrator'),
    ('browser', 'Code Browser'),
    ('observer', 'Observer')
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
    user = models.OneToOneField(User, related_name='profile', primary_key=True, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, null=True, blank=True, choices=ROLE_CHOICES)
    theme = models.CharField(max_length=25, null=True, choices=THEME_CHOICES, verbose_name=_('Code Editor Theme'))
    avatar = models.ImageField(upload_to=UUIDImageName('user/avatar'), null=True, blank=True, verbose_name=_('Avatar'))
    show_tags = models.BooleanField(default=True, verbose_name=_('Show tags'))
    institution = models.ForeignKey(Institution, null=True, verbose_name=_('Institution'), on_delete=models.SET_NULL)
    teams = models.ManyToManyField(Team, blank=True, related_name='profiles')
    rating_changes = models.ManyToManyField(Contest, through='RatingChange')
    compiler = models.ForeignKey(Compiler, null=True, verbose_name=_('Compiler'), on_delete=models.SET_NULL)
    points = models.PositiveIntegerField(verbose_name=_('Points'), null=False, default=0)
    email_notifications = models.BooleanField(
        verbose_name=_('Send email notifications'), default=True
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
        return self.role == 'admin'

    @property
    def is_observer(self):
        return self.role == 'observer'

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
    def solved_problems(self):
        return self.user.submissions.filter(result__name__iexact='accepted', hidden=False, status='normal')\
            .distinct('problem_id').count()

    @property
    def accepted_submissions(self):
        return self.user.submissions.filter(result__name__iexact='accepted', hidden=False, status='normal').count()

    @property
    def total_submissions(self):
        return self.user.submissions.filter(hidden=False).count()

    @staticmethod
    def sorted_by_ratings():
        return UserProfile.objects.annotate(rating_value=Coalesce(Sum('ratings__rating'), Value(0))). \
            order_by('-rating_value', '-points', 'pk').select_related('user')

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
    STATUS_CHOICES = [
        ('normal', 'normal'),
        ('frozen', 'frozen'),
        ('death', 'death')
    ]

    problem = models.ForeignKey(Problem, related_name='submissions', on_delete=models.CASCADE)
    instance = models.ForeignKey('ContestInstance', null=True, blank=True, related_name='submissions', on_delete=models.SET_NULL)
    date = models.DateTimeField()
    execution_time = models.IntegerField(default=0)
    memory_used = models.BigIntegerField(default=0)
    source = models.TextField()
    user = models.ForeignKey(User, related_name='submissions', on_delete=models.CASCADE)
    result = models.ForeignKey(Result, on_delete=models.CASCADE)
    compiler = models.ForeignKey(Compiler, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    judgement_details = models.TextField(null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='normal')

    @property
    def visible(self):
        return not self.hidden and (self.instance is None or self.instance.contest.visible)

    @staticmethod
    def visible_submissions(user):
        """Submissions to show in submission list"""
        if user_is_admin(user):
            return Submission.objects
        return Submission.objects \
            .filter(Q(hidden=False) & (Q(instance=None) | Q(instance__contest__visible=True)))

    def can_show_judgment_details_to(self, user):
        """Determine whether an user can see judgment details of the submission.
        An user can see judgment details only if:
        - The user is an administrator, or the submission is visible and the user
        is observer or
        - does not belong to a running instance and the submission.status='normal' and (is visible and public...
        or belongs to the user)
        """
        if user_is_admin(user) or (self.visible and user_is_observer(user)):
            return True

        if not self.instance or self.instance.is_past:
            return self.status == 'normal' and ((user.is_authenticated and self.user == user)
                                                or (self.visible and self.public))
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
        if user_is_admin(user) or (self.visible and user_is_observer(user)):
            return True

        if self.status == 'normal' and self.visible:
            return True

        return user.is_authenticated and self.user == user and self.status != 'death'

    def can_show_source_to(self, user):
        """Determine whether the user has the permissions to see the
        current submission's source code.  An user can see the source code only
        if:
         - The user is an administrator, or the submission is visible and the user
        is observer or
        - The submission is visible and public and does not belong to a running instance
        - The submission belongs to the user
        """
        if user_is_admin(user) or (self.visible and user_is_observer(user)):
            return True

        if self.visible and self.public and (not self.instance or self.instance.is_past):
            return True

        return user.is_authenticated and self.user == user

    def __str__(self):
        return str(self.id)


class Comment(models.Model):
    user = models.ForeignKey(User, related_name='comments', on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    body = models.TextField()
    html = models.TextField(default='')
    seen = models.ManyToManyField(User, related_name='seen_comments')

    def __init__(self, *args, **kwargs):
        super(Comment, self).__init__(*args, **kwargs)
        self.initial_body_value = self.body

    def save(self, *args, **kwargs):
        if not self.pk or (self.initial_body_value != self.body):
            matches = map(
                lambda match: (match.start(), match.end()),
                list(re.finditer('@[\S]+', self.body, re.S))
            )
            self.html = ''
            last_index, users = 0, set()
            for s, e in matches:
                if not last_index:
                    self.html = cgi.escape(self.body[:s], quote=True)
                username = self.body[(s + 1):e]
                try:
                    user = User.objects.get(username=username)
                    users.add(user)
                    url = render_to_string('mog/user/_link.html', {'user': user}).strip()
                    self.html += ' ' + url
                except:
                    self.html += cgi.escape(self.body[s:e], quote=True)
                last_index = e
            self.html += cgi.escape(self.body[last_index:], quote=True)
            # notify users about this comment
            for user in users:
                send_mail(
                    '{0} has mentioned you in a comment'.format(self.user.username),
                    message='<NO TEXT>',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                    html_message=render_to_string(
                        'mog/email/mention.html',
                        {
                            'user': self.user,
                            'comment': self,
                            'domain': 'http://matcomgrader.com'
                        }
                    )
                )
        # save now
        super(Comment, self).save(*args, **kwargs)

    def can_be_edited_by(self, user):
        return user_is_admin(user)

    def can_be_removed_by(self, user):
        return user_is_admin(user)


class ContestInstance(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, related_name='instances', on_delete=models.CASCADE)
    team = models.ForeignKey(Team, null=True, blank=True, related_name='instances', on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, related_name='instances', on_delete=models.CASCADE)
    start_date = models.DateTimeField(null=True, blank=True)
    real = models.BooleanField()
    group = models.CharField(max_length=64, null=True, blank=True, verbose_name=_('Group name'))
    render_team_description_only = models.BooleanField(default=False,
        verbose_name=_('If true, render the team without members and only displaying the description on hover'))

    def __str__(self):
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
        return (timezone.now() - self.start_date).total_seconds() * 100 // self.contest.duration.total_seconds()

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


class Clarification(models.Model):
    contest = models.ForeignKey(
        Contest,
        on_delete=models.CASCADE,
        related_name='clarifications',
        verbose_name=_('Contest')
    )
    problem = models.ForeignKey(
        Problem,
        on_delete=models.SET_NULL,
        related_name='clarifications',
        blank=True, null=True,
        verbose_name=_('Problem')
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='clarifications',
        null=True,
    )
    fixer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        default=None, null=True,
    )
    seen = models.ManyToManyField(
        User,
        related_name='seen_clarifications'
    )
    public = models.BooleanField(
        default=False,
        verbose_name=_('Public')
    )
    question = models.CharField(
        max_length=2048,
        verbose_name=_('Question')
    )
    answer = models.TextField(
        blank=True, null=True,
        verbose_name=_('Answer')
    )
    asked_date = models.DateTimeField(auto_now_add=True)
    answered_date = models.DateTimeField(null=True)

    def save(self, *args, **kwargs):
        new_instance = self.pk is None
        super(Clarification, self).save(*args, **kwargs)
        if new_instance:
            report_clarification(clarification=self)

    def formset(self):
        from mog.forms import ClarificationExtendedForm
        return ClarificationExtendedForm(
            instance=self
        )


class UserFeedback(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='feedbacks'
    )
    submitted_date = models.DateTimeField(
        auto_now_add=True
    )
    subject = models.CharField(
        max_length=1024,
        verbose_name=_('Subject')
    )
    description = models.TextField(
        blank=True, null=True,
        verbose_name=_('Description')
    )
    screenshot = models.ImageField(
        upload_to=UUIDImageName('screenshot'),
        null=True,
        blank=True,
        verbose_name=_('Screenshot')
    )

    def __str__(self):
        return self.subject
