from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View, generic

from api.models import Submission, Compiler, Problem, Result, Contest


from mog.utils import user_is_admin


class SubmissionListView(generic.ListView):
    """
    Use template_name from URLconf in order
    to  reuse this view in 'submissions' and
    'contest submissions'.
    """
    paginate_by = 30

    def str_value(self, parameter):
        value = self.request.GET.get(parameter, '').strip()
        return value if len(value) > 0 else None

    def int_value(self, parameter):
        value = self.str_value(parameter)
        return int(value) if value and value.isdigit() else None

    def get_queryset(self):
        queryset = Submission.objects
        contest = self.int_value('contest')
        result = self.int_value('result')
        compiler = self.int_value('compiler')
        username = self.str_value('username')
        problem = self.str_value('problem')
        if contest:
            queryset = queryset.filter(problem__contest=contest)
        if result:
            queryset = queryset.filter(result_id=result)
        if compiler:
            queryset = queryset.filter(compiler_id=compiler)
        if username:
            queryset = queryset.filter(user__username__contains=username)
        if problem:
            queryset = queryset.filter(problem__title__contains=problem)
        return queryset.order_by('-id').select_related('user', 'result')

    def get_context_data(self, **kwargs):
        context = super(SubmissionListView, self).get_context_data(**kwargs)
        for parameter in ['username', 'problem', 'result', 'compiler', 'contest']:
            value = self.str_value(parameter)
            if value:
                if 'query' not in context:
                    context['query'] = {}
                context['query'][parameter] = value

        contest_id = self.int_value('contest')

        if contest_id:
            contest = get_object_or_404(Contest, pk=contest_id)
            context['contest'] = contest

        context['results'] = Result.objects.all()
        context['compilers'] = Compiler.objects.all()
        return context


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
        if file is not None:
            source = file.read()
        if not source:
            return redirect('mog:submit', problem_id=problem.id)
        try:
            instance = request.user.instances.get(contest=problem.contest)
            if not instance.is_running:
                instance = None
        except:
            instance = None
        submission = Submission(problem=problem, source=source,
                                user=request.user, compiler=compiler,
                                result=Result.objects.get(name__iexact='pending'),
                                instance=instance)
        if user_is_admin(request.user):
            submission.hidden = True
        submission.save()
        return redirect(
            reverse('mog:contest_submissions') + '?contest={0}'.format(problem.contest_id)
        )
