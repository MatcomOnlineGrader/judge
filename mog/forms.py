import json

from captcha.fields import CaptchaField
from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from registration.forms import RegistrationFormNoFreeEmail, RegistrationFormUniqueEmail

from api.models import UserProfile, UserFeedback, User, Post, Contest, Problem, Clarification
from mog.utils import secure_html


class UserProfileForm(forms.ModelForm):
    avatar = forms.ImageField(widget=forms.FileInput, required=False)

    class Meta:
        model = UserProfile
        fields = ['avatar', 'theme', 'institution', 'compiler', 'show_tags', 'email_notifications']

    def save(self, commit=True):
        if self.cleaned_data['avatar']:
            self.instance.avatar = self.cleaned_data['avatar']
        self.instance.theme = self.cleaned_data['theme']
        self.instance.show_tags = self.cleaned_data['show_tags']
        self.instance.institution = self.cleaned_data['institution']
        self.instance.compiler = self.cleaned_data['compiler']
        if commit:
            self.instance.save()


class UserForm(forms.ModelForm):
    password_1 = forms.CharField(label=_('Password'), widget=forms.PasswordInput, required=False)
    password_2 = forms.CharField(label=_('Password confirmation'), widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name']

    def clean_password_2(self):
        password_1 = self.cleaned_data.get("password_1")
        password_2 = self.cleaned_data.get("password_2")
        if password_1 != password_2:
            raise forms.ValidationError("Passwords don't match")
        return password_2

    def save(self, commit=True):
        self.instance.first_name = self.cleaned_data['first_name']
        self.instance.last_name = self.cleaned_data['last_name']
        if self.cleaned_data["password_2"]:
            self.instance.set_password(self.cleaned_data["password_2"])
        if commit:
            self.instance.save()


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['name', 'body', 'meta_description', 'meta_image']

    def clean_body(self):
        return secure_html(self.cleaned_data['body'])


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = ['name', 'code', 'description', 'start_date', 'end_date', 'visible', 'frozen_time',
                  'death_time', 'group', 'closed', 'allow_teams']

    def clean_description(self):
        return secure_html(self.cleaned_data['description'])

    def clean(self):
        super(ContestForm, self).clean()
        start_date, end_date = self.cleaned_data.get('start_date'),\
                               self.cleaned_data.get('end_date')
        if start_date and end_date and start_date >= end_date:
            self.add_error('start_date', _('Start date must be less than end date'))
        death_time, frozen_time = self.cleaned_data.get('death_time'), \
                                  self.cleaned_data.get('frozen_time')
        if death_time is not None and frozen_time is not None:
            if frozen_time < death_time:
                self.add_error('frozen_time', _('Frozen time must be greater or equal than death time'))
            if start_date and end_date and (end_date - start_date).total_seconds() < death_time * 60:
                self.add_error('death_time', _('Death time must be less or equal than contest duration'))


PROBLEM_FIELDS_WITHOUT_CONTEST = [
    'title',
    'body',
    'input',
    'output',
    'hints',
    'time_limit',
    'memory_limit',
    'multiple_limits',
    'checker',
    'position',
    'balloon',
    'letter_color',
    'tags',
    'compilers'
]


class ProblemInContestForm(forms.ModelForm):
    """Used to create a new problem when a contest is specified and no
    need to add an input for it."""
    class Meta:
        model = Problem
        fields = PROBLEM_FIELDS_WITHOUT_CONTEST

    def clean_multiple_limits(self):
        def json_is_correct(content):
            if len(content.strip()) == 0:
                return True
            try:
                json.loads(content)
            except:
                return False
            return True
        limits = self.cleaned_data.get('multiple_limits')
        if not json_is_correct(limits):
            raise forms.ValidationError('The JSON does not have a correct format')
        return limits


PROBLEM_FIELDS_WITH_CONTEST = PROBLEM_FIELDS_WITHOUT_CONTEST \
    + ['contest']


class ProblemForm(ProblemInContestForm):
    """Contains all field needed to edit a Problem, this form includes
    the contest field that can be changed only in the modify problem
    view."""
    class Meta:
        model = Problem
        fields = PROBLEM_FIELDS_WITH_CONTEST


class MOGRegistrationForm(RegistrationFormNoFreeEmail, RegistrationFormUniqueEmail):
    """https://github.com/ivolo/disposable-email-domains/blob/master/index.json"""
    bad_domains = json.load(open('disposable.json', 'r'))

    def clean_email(self):
        RegistrationFormNoFreeEmail.clean_email(self)
        RegistrationFormUniqueEmail.clean_email(self)
        return self.cleaned_data['email']


class MOGRegistrationFormWithCaptcha(MOGRegistrationForm):
    captcha = CaptchaField()


class ClarificationForm(forms.ModelForm):
    question = forms.CharField(
        widget=forms.Textarea,
        label=_('Question')
    )

    class Meta:
        model = Clarification
        fields = ['problem', 'question']

    def __init__(self, contest=None, *args, **kwargs):
        super(ClarificationForm, self).__init__(*args, **kwargs)
        self.contest = contest or self.instance.contest
        self.fields['problem'].choices = [(None, '----- General -----')]
        for problem in self.contest.problems.order_by('position'):
            self.fields['problem'].choices.append((problem.pk, problem.full_title))
        self.fields['problem'].initial = self.instance.problem if self.instance else None

    def clean_question(self):
        return self.cleaned_data['question'].strip()

    def clean(self):
        super(ClarificationForm, self).clean()
        problem = self.cleaned_data['problem']
        if problem and problem.contest != self.contest:
            self.add_error('problem', _('Problem not included in contest'))


class ClarificationExtendedForm(ClarificationForm):
    answer = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4}),
        label=_('Answer')
    )

    class Meta:
        model = Clarification
        fields = ['problem', 'question', 'answer', 'public']



class UserFeedbackForm(forms.ModelForm):
    class Meta:
        model = UserFeedback
        fields = ['subject', 'description', 'screenshot']


class ImportBaylorForm(forms.Form):
    zip_baylor = forms.FileField(label = 'Upload file',
        help_text = mark_safe(_('Load the ZIP file from Baylor. The file must have the .tab files <i>(School.tab, Site.tab, Team.tab, Person.tab, and TeamPerson.tab)</i>.')))
    prefix_baylor = forms.CharField(max_length = 20, label = 'Prefix', help_text = mark_safe(_('Prefix to add to each official user account. Example: <b>2021CFQ</b>.<br>\
        Users created will be named as <b>2021CFQ_icpc_[#]</b>.<br>\
        <span style="color: red;">Make sure you use the same <i>prefix</i> to the same contest and related (warmup and real)</span>')))
    select_pending_teams_baylor = forms.BooleanField(required = False, label = 'Include pending teams')


class ImportGuestTeamsForm(forms.Form):
    csv_teams = forms.FileField(label = 'Upload file',
        help_text = mark_safe(_('Load the CSV file with all Guest Teams. The file must have the following columns: <i>team_name, institution, coach, participant1, participant2, participant3, and group</i>.')))
    prefix_team = forms.CharField(max_length = 20, label = 'Prefix', help_text = mark_safe(_('Prefix to add to each guest user account. Example: <b>2021CFQ</b>.<br>\
        Users created will be named as <b>2021CFQ_guest_[#]</b>.<br>\
        <span style="color: red;">Make sure you use the same <i>prefix</i> to the same contest and related (warmup and real)</span>')))


class ImportPermissionForm(forms.Form):
    csv_permission = forms.FileField(label = 'Upload file',
        help_text = mark_safe(_('Load the CSV file with all User Permissions. The file must have the following columns: <i>username, role, and granted</i>.')))
