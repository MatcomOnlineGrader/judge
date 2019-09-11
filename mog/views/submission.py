from datetime import timedelta

from django.utils import timezone
from django.views.decorators.http import require_http_methods

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.utils.translation import ugettext_lazy as _

from api.models import Submission, Compiler, Problem, Result
from mog.helpers import filter_submissions, get_paginator

from mog.gating import user_is_admin, user_is_judge_in_contest


def submissions(request):
    submission_list, query = filter_submissions(
        request.user,
        problem=request.GET.get('problem'), contest=request.GET.get('contest'),
        username=request.GET.get('username'), result=request.GET.get('result'),
        compiler=request.GET.get('compiler')
    )
    submissions = get_paginator(submission_list, 30, request.GET.get('page'))
    return render(request, 'mog/submission/index.html', {
        'submissions': submissions,
        'results': Result.get_all_results(),
        'compilers': Compiler.get_all_compilers(),
        'query': query
    })


def submission(request, submission_id):
    submission = get_object_or_404(Submission, pk=submission_id)
    if not submission.can_show_source_to(request.user):
        raise Http404()
    return render(request, 'mog/submission/detail.html', {
        'submission': submission,
    })


class Submit(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)

        if not problem.contest.can_be_seen_by(request.user):
            raise Http404()

        return render(request, 'mog/submit/submit.html', {
            'problem': problem, 'compilers': Compiler.objects.order_by('id'),
        })

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        problem = request.POST.get('problem')
        compiler = request.POST.get('compiler')
        source = request.POST.get('source')
        file = request.FILES.get('file')
        problem = get_object_or_404(Problem, pk=problem)
        compiler = get_object_or_404(Compiler, pk=compiler)
        date = timezone.now()

        if not user_is_admin(request.user) and not user_is_judge_in_contest(request.user, problem.contest) and not problem.contest.visible:
            raise Http404()

        if not user_is_admin(request.user) and not user_is_judge_in_contest(request.user, problem.contest) and compiler not in problem.compilers.all():
            msg = _(u'Invalid language choice')
            messages.warning(request, msg, extra_tags='danger')
            return redirect('mog:submit', problem.id)

        if file is not None:
            source = file.read().decode('utf8')

        if not source:
            msg = _(u'Empty source code')
            messages.info(request, msg, extra_tags='info')
            return redirect('mog:submit', problem_id=problem.id)

        instance = problem.contest.registration(request.user)
        if instance and not instance.is_running_at(date):
            instance = None

        if not user_is_admin(request.user) and not user_is_judge_in_contest(request.user, problem.contest) \
                and (not instance) and problem.contest.is_running:
            msg = _(u'You cannot submit because you are not registered in the contest.')
            messages.info(request, msg, extra_tags='info')
            return redirect('mog:contest_problems', problem.contest.id)

        if (not user_is_admin(request.user) and not user_is_judge_in_contest(request.user, problem.contest)) \
                and problem.contest.needs_unfreeze and problem.contest.is_past:
            msg = _(u'You cannot submit because the contest is still frozen.')
            messages.info(request, msg, extra_tags='info')
            return redirect('mog:contest_problems', problem.contest.id)

        # check if this submission was sent twice too quick
        previous = Submission.objects.filter(user=request.user)\
            .order_by('date').last()

        if previous and (date - previous.date).total_seconds() < 5:
            if (previous.problem == problem) and (previous.compiler == compiler) \
                    and (previous.source == source):
                msg = _(u'Sending same submission twice too quickly.')
                messages.info(request, msg, extra_tags='warning')
                return redirect('mog:contest_submissions', problem.contest.id)

        # determine whether the current submission was sent in normal,
        # froze or death time.
        status = 'normal'
        if instance and instance.real:
            contest = instance.contest
            if date < contest.end_date - timedelta(minutes=contest.frozen_time):
                status = 'normal'
            elif date < contest.end_date - timedelta(minutes=contest.death_time):
                status = 'frozen'
            else:
                status = 'death'
        submission = Submission(
            problem=problem,
            source=source,
            user=request.user,
            compiler=compiler,
            result=Result.objects.get(name__iexact='pending'),
            instance=instance,
            date=date,
            status=status
        )
        if user_is_admin(request.user) or user_is_judge_in_contest(request.user, problem.contest):
            submission.hidden = True
        submission.save()

        # Set default compiler after a submission
        if hasattr(request.user, 'profile'):
            profile = request.user.profile
            if profile.compiler_id != compiler.id:
                profile.compiler = compiler
                profile.save()

        return redirect('mog:contest_submissions', problem.contest_id)


@login_required
@require_http_methods(["POST"])
def rejudge(request, submission_id):
    submission = get_object_or_404(Submission, pk=submission_id)
    if not user_is_admin(request.user) and not user_is_judge_in_contest(request.user, submission.problem.contest):
        return HttpResponseForbidden()
    submission.result = Result.objects.get(name__iexact='pending')
    submission.save()
    # TODO: Find a better way to redirect to previous page.
    return redirect(request.META.get('HTTP_REFERER', '/'))
