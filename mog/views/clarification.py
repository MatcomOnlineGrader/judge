from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from api.models import Contest, Clarification
from mog.forms import ClarificationForm, ClarificationExtendedForm
from mog.gating import user_is_admin, user_is_judge_in_contest
from mog.webhooks import push_clarification_to_webhooks


@login_required
@require_http_methods(["POST"])
def clarification_create(request):
    contest = get_object_or_404(Contest, pk=request.POST.get("contest"))
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    error = None
    if not user_is_admin(request.user) and not user_is_judge_in_contest(
        request.user, contest
    ):
        if not contest.is_running:
            error = _("You cannot ask in a contest that is not running")
        elif not contest.real_registration(request.user):
            error = _(
                "You cannot ask questions because you are not registered in the contest."
            )
    if error:
        messages.error(request, error, extra_tags="danger")
    else:
        form = ClarificationForm(contest=contest, data=request.POST)
        if not form.is_valid():
            return render(
                request,
                "mog/contest/clarifications.html",
                {
                    "contest": contest,
                    "clarifications": contest.visible_clarifications(request.user),
                    "form": form,
                },
            )

        clarification = Clarification.objects.create(
            contest=contest,
            problem=form.cleaned_data["problem"],
            sender=request.user,
            question=form.cleaned_data["question"],
        )

        if user_is_admin(request.user) or user_is_judge_in_contest(
            request.user, contest
        ):
            answer = request.POST.get("answer")
            public = request.POST.get("public", "") == "on"
            if answer:
                clarification.answer = answer
                clarification.public = public
                clarification.fixer = request.user
                clarification.answered_date = timezone.now()
                clarification.seen.clear()
                clarification.save()

        push_clarification_to_webhooks(clarification, create=True)

        messages.success(
            request,
            _(
                "Request for clarification sent successfully."
                " Reload this page to see the answer given to you."
            ),
        )
    if "next" in request.POST:
        return redirect(request.POST["next"])
    return redirect(reverse("mog:contest_clarifications", args=(contest.id,)))


@login_required
@require_http_methods(["POST"])
def clarification_edit(request, clarification_id):
    clarification = get_object_or_404(Clarification, pk=clarification_id)
    if not user_is_admin(request.user) and not user_is_judge_in_contest(
        request.user, clarification.contest
    ):
        raise Http404()

    formset = ClarificationExtendedForm(instance=clarification, data=request.POST)
    if formset.is_valid():
        formset.save()
        clarification.fixer = request.user
        clarification.answered_date = timezone.now()
        clarification.seen.clear()
        clarification.save()

        push_clarification_to_webhooks(clarification, create=False)

        messages.success(request, _("Clarification successfully edited"))
    else:
        messages.error(request, _("Unable to edit clarification"))
    return redirect(
        reverse("mog:contest_clarifications", args=(clarification.contest_id,))
    )
