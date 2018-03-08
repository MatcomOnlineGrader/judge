from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_http_methods

from api.models import Contest, Clarification
from mog.forms import ClarificationForm, ClarificationExtendedForm
from mog.utils import user_is_admin


@login_required
@require_http_methods(["POST"])
def clarification_create(request):
    contest = get_object_or_404(Contest, pk=request.POST.get('contest'))
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    error = None
    if not user_is_admin(request.user):
        if not contest.is_running:
            error = _(u'You cannot ask in a contest that is not running')
        elif contest.real_registration(request.user):
            error = _(u'You cannot ask questions because you are not registered in the contest.')
    if error:
        messages.error(request, error, extra_tags='danger')
    else:
        form = ClarificationForm(
            contest=contest,
            data=request.POST
        )
        if not form.is_valid():
            return render(request, 'mog/contest/clarifications.html', {
                'contest': contest,
                'clarifications': contest.visible_clarifications(request.user),
                'form': form
            })
        Clarification.objects.create(
            contest=contest,
            problem=form.cleaned_data['problem'],
            sender=request.user,
            question=form.cleaned_data['question']
        )
        messages.success(
            request, _(u'Request for clarification sent successfully.'
                       u' Reload this page to see the answer given to you.')
        )
    if 'next' in request.POST:
        return redirect(request.POST['next'])
    return redirect(reverse('mog:contest_clarifications', args=(contest.id,)))


@login_required
@require_http_methods(["POST"])
def clarification_edit(request, clarification_id):
    if not user_is_admin(request.user):
        raise Http404()
    clarification = get_object_or_404(
        Clarification, pk=clarification_id
    )
    formset = ClarificationExtendedForm(
        instance=clarification,
        data=request.POST
    )
    if formset.is_valid():
        formset.save()
        clarification.fixer = request.user
        clarification.answered_date = timezone.now()
        clarification.seen.clear()
        clarification.save()
        messages.success(request, _(u'Clarification successfully edited'))
    else:
        messages.error(request, _(u'Unable to edit clarification'))
    return redirect(
        reverse('mog:contest_clarifications', args=(clarification.contest_id, ))
    )
