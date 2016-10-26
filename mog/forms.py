from django import forms
from api.models import UserProfile, User, Post, Contest, Problem


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


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        exclude = []


class ProblemForm(forms.ModelForm):
    class Meta:
        model = Problem
        exclude = ['slug']
