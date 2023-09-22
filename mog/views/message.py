import django.contrib.messages as msgs
from django.views.decorators.http import require_http_methods
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

from api.models import Message
from mog.decorators import public_actions_required


@public_actions_required
@login_required
@require_http_methods(["POST"])
def send_message(request, user_id):
    """Send a message to <user_id> from <request.user>"""
    subject = request.POST.get("subject", "").strip()
    if len(subject) == 0:
        subject = "(no subject)"
    body = request.POST.get("body")
    source = request.user
    target = get_object_or_404(User, pk=user_id)
    message = Message(source=source, target=target, subject=subject, body=body)
    message.save()

    msgs.success(request, "Message sent successfully!", extra_tags="success")

    redirect_url = request.POST.get("redirect_url", "").strip()

    if len(redirect_url) != 0:
        return redirect(redirect_url)
    return redirect("mog:user", user_id=target.id)
