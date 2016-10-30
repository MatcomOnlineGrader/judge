from django import forms
from django.utils.translation import ugettext_lazy as _

from api.models import UserProfile, User, Post, Contest, Problem
from mog.utils import secure_html


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar', 'theme', 'show_tags', 'institution', 'compiler']

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
    password_1 = forms.CharField(label='Password', widget=forms.PasswordInput, required=False)
    password_2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def clean_password_2(self):
        password_1 = self.cleaned_data.get("password_1")
        password_2 = self.cleaned_data.get("password_2")
        if password_1 != password_2:
            raise forms.ValidationError("Passwords don't match")
        return password_2

    def save(self, commit=True):
        self.instance.email = self.cleaned_data['email']
        self.instance.first_name = self.cleaned_data['first_name']
        self.instance.last_name = self.cleaned_data['last_name']
        if self.cleaned_data["password_2"]:
            self.instance.set_password(self.cleaned_data["password_2"])
        if commit:
            self.instance.save()


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['name', 'body']

    def clean_body(self):
        return secure_html(self.cleaned_data['body'])


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = ['name', 'code', 'description', 'start_date', 'end_date', 'visible', 'frozen_time',
                  'death_time', 'closed', 'allow_teams']

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


class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        fields = ['title', 'body', 'input', 'output', 'hints', 'time_limit',
                  'memory_limit', 'checker', 'position', 'balloon', 'contest',
                  'tags']
