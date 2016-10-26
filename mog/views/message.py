import django.contrib.messages as msgs
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

from api.models import Message
from mog.utils import user_is_admin


@login_required
@require_http_methods(["POST"])
def send_message(request, user_id):
    """Send a message to <user_id> from <request.user>"""
    subject = request.POST.get('subject', '').strip()
    if len(subject) == 0:
        subject = '(no subject)'
    body = request.POST.get('body')
    source = request.user
    target = get_object_or_404(User, pk=user_id)
    Message.objects.create(
        source=source,
        target=target,
        subject=subject,
        body=body
    )
    msgs.success(request, 'Message sent successfully!', extra_tags='success')
    return redirect('mog:user', user_id=target.id)
