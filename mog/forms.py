from django import forms
from api.models import UserProfile, User, Post, Contest, Problem


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar', 'theme', 'show_tags', 'institution', 'compiler']


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['name', 'body']


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        exclude = []


class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        exclude = ['slug']
