from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_http_methods

from api.models import UserFeedback
from mog.forms import UserFeedbackForm


@login_required
@require_http_methods(["POST"])
def feedback_create(request):
    form = UserFeedbackForm(request.POST, request.FILES)
    if form.is_valid():
        data = form.cleaned_data
        UserFeedback.objects.create(
            sender=request.user,
            subject=data['subject'],
            description=data['description'],
            screenshot=data['screenshot']
        )
        messages.success(request, _('Feedback received'), extra_tags='success')
    return redirect(request.POST.get('next', '/'))
