from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext_lazy as _
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods

from api.models import UserFeedback
from mog.forms import UserFeedbackForm
from mog.gating import user_is_admin
from mog.helpers import get_paginator
from mog.tasks import (
    report_feedback,
    report_feedback_to_user,
    report_feedback_to_assigned,
)


@login_required
@require_http_methods(["POST"])
def feedback_create(request):
    form = UserFeedbackForm(request.POST, request.FILES)
    if form.is_valid():
        data = form.cleaned_data
        feedback = UserFeedback.objects.create(
            sender=request.user,
            subject=data["subject"],
            description=data["description"],
            screenshot=data["screenshot"],
        )
        report_feedback(feedback)
        messages.success(request, _("Feedback received"), extra_tags="success")
    return redirect(request.POST.get("next", "/"))


@login_required
def feedback_list(request):
    feedback_list, query = filter_feedbacks(
        request.user,
        subject=request.GET.get("subject"),
        status=request.GET.get("status"),
    )

    feedbacks = get_paginator(feedback_list, 30, request.GET.get("page"))
    status_choices = UserFeedback.STATUS_CHOICES

    return render(
        request,
        "mog/feedback/index.html",
        {"feedbacks": feedbacks, "query": query, "status_choices": status_choices},
    )


def filter_feedbacks(user_who_request, subject=None, status=None):
    if user_is_admin(user_who_request):
        queryset = UserFeedback.objects
    else:
        queryset = UserFeedback.objects.filter(
            Q(sender=user_who_request) | Q(assigned=user_who_request)
        )

    query = {}
    if subject:
        # ignore case-sensitive
        queryset = queryset.filter(subject__icontains=subject)
        query["subject"] = subject  # no encode needed
    if status:
        queryset = queryset.filter(status=status)
        query["status"] = status  # no encode needed

    return queryset.order_by("-submitted_date"), query


class FeedbackView(View):
    @method_decorator(login_required)
    def get(self, request, feedback_id, *args, **kwargs):
        feedback = get_object_or_404(UserFeedback, pk=feedback_id)

        if (
            not user_is_admin(request.user)
            and feedback.sender != request.user
            and feedback.assigned != request.user
        ):
            return HttpResponseForbidden()

        status_choices = UserFeedback.STATUS_CHOICES

        admins = User.objects.filter(
            Q(profile__role="admin") | Q(profile__role="judge")
        ).order_by("profile__role")

        return render(
            request,
            "mog/feedback/feedback.html",
            {"feedback": feedback, "status_choices": status_choices, "admins": admins},
        )

    @method_decorator(login_required)
    def post(self, request, feedback_id, *args, **kwargs):
        feedback = get_object_or_404(UserFeedback, pk=feedback_id)

        if (
            not user_is_admin(request.user)
            and feedback.sender != request.user
            and feedback.assigned != request.user
        ):
            return HttpResponseForbidden()

        subject = None
        status = request.POST.get("status")
        assigned = request.POST.get("assigned")
        reassigned = False

        if status:
            if status != feedback.status:
                if status == "open":
                    subject = "Your feedback have been Opened"
                elif status == "in_progress":
                    subject = "Your feedback have been set to In Progress"
                elif status == "closed":
                    subject = "Your feedback have been Closed"
            feedback.status = status

        if assigned and assigned != "unassigned":
            try:
                user_assigned = User.objects.get(id=int(assigned))
                if user_assigned != feedback.assigned:
                    reassigned = True
                feedback.assigned = user_assigned
            except:
                pass
        elif assigned == "unassigned":
            feedback.assigned = None

        if subject:
            report_feedback_to_user(feedback, subject)

        if reassigned:
            report_feedback_to_assigned(feedback)

        feedback.save()
        messages.success(request, _("Feedback edited"), extra_tags="success")

        return redirect("mog:feedback_list")
