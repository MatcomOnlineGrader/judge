import threading

from django.contrib import messages
from django.shortcuts import redirect

from mog.gating import public_actions_blocked, user_is_admin


def asynchronous(func):
    def wrapper(*args, **kwargs):
        threading.Thread(target=func, args=args, kwargs=kwargs).start()
    return wrapper


def public_actions_required(function):
    def new_function(request, *args, **kwargs):
        if public_actions_blocked() and not user_is_admin(request.user):
            messages.warning(request, 'This action is currently blocked!', extra_tags='warning secure')
            return redirect('mog:index')
        else:
            return function(request, *args, **kwargs)
    return new_function
