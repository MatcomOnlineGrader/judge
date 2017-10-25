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

from mog.utils import user_is_admin


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
        if not user_is_admin(request.user) and not problem.contest.visible:
            return Http404()
        if not user_is_admin(request.user) and compiler not in problem.compilers.all():
            msg = _(u'Invalid language choice')
            messages.warning(request, msg, extra_tags='danger')
            return redirect('mog:submit', problem.id)
        if file is not None:
            source = file.read()
        if not source:
            msg = _(u'Empty source code')
            messages.info(request, msg, extra_tags='info')
            return redirect('mog:submit', problem_id=problem.id)
        instance = problem.contest.registration(request.user)
        if instance and not instance.is_running:
            instance = None
        if (not user_is_admin(request.user)) and (not instance) and problem.contest.is_running:
            msg = _(u'You cannot submit because you are not registered in the contest.')
            messages.info(request, msg, extra_tags='info')
            return redirect('mog:contest_problems', problem.contest.id)
        submission = Submission(problem=problem, source=source,
                                user=request.user, compiler=compiler,
                                result=Result.objects.get(name__iexact='pending'),
                                instance=instance)
        if user_is_admin(request.user):
            submission.hidden = True
        submission.save()
        return redirect('mog:contest_submissions', problem.contest_id)


@login_required
@require_http_methods(["POST"])
def rejudge(request, submission_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    submission = get_object_or_404(Submission, pk=submission_id)
    submission.result = Result.objects.get(name__iexact='pending')
    submission.save()
    # TODO: Find a better way to redirect to previous page.
    return redirect(request.META.get('HTTP_REFERER', '/'))
