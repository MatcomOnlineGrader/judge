from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from django.contrib import messages

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views import View


class Register(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'mog/account/register.html')

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password_1 = request.POST.get('password_1')
        password_2 = request.POST.get('password_1')

        msgs = []

        if None in [username, email, password_1, password_2]:
            msgs.append(u'All fields are required!')

        try:
            EmailValidator()(email)
        except ValidationError:
            msgs.append(u'Enter a valid email!')

        if password_1 != password_2:
            msgs.append(u'Passwords does not match!')

        if User.objects.filter(username=username).count() > 0:
            msgs.append(u'User with username "{0}" already exist!'.format(username))

        if User.objects.filter(email=email).count() > 0:
            msgs.append(u'User with email "{0}" already exist!'.format(email))

        if msgs:
            for msg in msgs:
                messages.success(request, msg, extra_tags='danger')
            return render(request, 'mog/account/register.html', {
                'username': username, 'email': email
            })

        messages.success(request, 'Welcome and enjoy solving problems!', extra_tags='success')

        user = User(username=username,
                    password=make_password(password_1),
                    email=email)

        user.save()
        login(request, user)

        return redirect('mog:user_edit', user_id=user.id)


class Login(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'mog/account/login.html', {
            'next': request.GET.get('next')
        })

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me') == 'on'
        next = request.POST.get('next')
        user = authenticate(username=username, password=password)
        if not user:
            msg = u'Invalid username or password!'
            messages.success(request, msg, extra_tags='danger')
            return render(request, 'mog/account/login.html', {
                'next': next, 'username': username, 'remember_me': remember_me
            })
        login(request, user)
        # if remember_me is set then current session will
        # expire in one year. In other case, session cookie
        # will expire when user's web browser is closed.
        value = 360 * 24 * 60 * 60 if remember_me else 0
        request.session.set_expiry(value)
        return redirect(next or 'mog:index')


class Logout(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('mog:index')