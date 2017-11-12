from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View, generic
from django.views.decorators.http import require_http_methods

from api.models import Problem, Tag
from mog.forms import ProblemForm
from mog.utils import user_is_admin, get_tests, handle_tests,\
    handle_remove_test, test_content, write_to_test, fix_problem_folder


@login_required
@require_http_methods(["POST"])
def remove_problem(request, problem_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    problem = get_object_or_404(Problem, pk=problem_id)
    problem.delete()
    msg = u'Problem "{0}" removed successfully!'.format(problem.title)
    messages.success(request, msg, extra_tags='success')
    return redirect('mog:contest_problems', contest_id=problem.contest_id)


@login_required
@require_http_methods(["POST"])
def remove_test(request, problem_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    problem = get_object_or_404(Problem, pk=problem_id)
    folder, test = request.POST.get('folder'),\
                   request.POST.get('test')
    if folder not in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        msg = 'Invalid folder value, it mus be one of: "inputs", "outputs", "sample inputs", "sample outputs"'
        messages.success(request, msg, extra_tags='danger')
    elif not test:
        msg = 'Test name not provided!'
        messages.success(request, msg, extra_tags='danger')
    else:
        msg = 'Test "%s/%s" removed successfully!' % (folder, test)
        messages.success(request, msg, extra_tags='success')
        handle_remove_test(problem, folder, test)
    return redirect('mog:problem_tests', problem_id=problem.id)


class TestEditView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        folder = request.GET.get('folder')
        test = request.GET.get('test')
        problem = get_object_or_404(Problem, pk=problem_id)
        content = test_content(problem, folder, test)
        if not content:
            raise Http404()
        return render(request, 'mog/test/edit.html', {
            'folder': folder, 'test': test, 'problem': problem, 'content': content
        })

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        folder = request.POST.get('folder')
        test = request.POST.get('test')
        problem = get_object_or_404(Problem, pk=problem_id)
        content = request.POST.get('content', '')
        write_to_test(problem, folder, test, content)
        return redirect('mog:problem_tests', problem_id=problem.id)


def problem(request, problem_id, slug):
    problem = get_object_or_404(Problem, pk=problem_id)
    if not problem.contest.can_be_seen_by(request.user):
        raise Http404()
    if problem.slug != slug:
        return redirect('mog:problem', problem_id=problem_id, slug=problem.slug, permanent=True)
    si_folder, so_folder = 'sample inputs', 'sample outputs'
    si = [test_content(problem, si_folder, test) for test in get_tests(problem, si_folder)]
    so = [test_content(problem, so_folder, test) for test in get_tests(problem, so_folder)]
    return render(request, 'mog/problem/detail.html', {
        'problem': problem, 'samples': zip(si, so)
    })


class ProblemTestsView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        problem = get_object_or_404(Problem, pk=problem_id)
        return render(request, 'mog/problem/tests.html', {
            'problem': problem,
            'sample_inputs': get_tests(problem, 'sample inputs'),
            'sample_outputs': get_tests(problem, 'sample outputs'),
            'inputs': get_tests(problem, 'inputs'),
            'outputs': get_tests(problem, 'outputs'),
        })

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        problem = get_object_or_404(Problem, pk=problem_id)
        handle_tests(problem, request.FILES.getlist('sample_inputs'), 'sample inputs')
        handle_tests(problem, request.FILES.getlist('sample_outputs'), 'sample outputs')
        handle_tests(problem, request.FILES.getlist('inputs'), 'inputs')
        handle_tests(problem, request.FILES.getlist('outputs'), 'outputs')
        return redirect('mog:problem_tests', problem_id=problem.id)


class ProblemCreateView(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            HttpResponseForbidden()
        return render(request, 'mog/problem/create.html', {
            'form': ProblemForm()
        })

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            HttpResponseForbidden()
        form = ProblemForm(request.POST)
        if not form.is_valid():
            return render(request, 'mog/problem/create.html', {
                'form': form
            })
        data = form.cleaned_data
        problem = Problem(
            title=data['title'],
            body=data['body'],
            input=data['input'],
            output=data['output'],
            hints=data['hints'],
            time_limit=data['time_limit'],
            memory_limit=data['memory_limit'],
            checker=data['checker'],
            position=data['position'],
            balloon=data['balloon'],
            letter_color=data['letter_color'],
            contest=data['contest'],
        )
        problem.save()
        problem.tags = data['tags']
        problem.compilers = data['compilers']
        fix_problem_folder(problem)
        return redirect('mog:problem', problem_id=problem.id, slug=problem.slug)


class ProblemEditView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        problem = get_object_or_404(Problem, pk=problem_id)
        return render(request, 'mog/problem/edit.html', {
            'form': ProblemForm(instance=problem), 'problem': problem,
        })

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        if not user_is_admin(request.user):
            HttpResponseForbidden()
        form = ProblemForm(request.POST)
        if not form.is_valid():
            return render(request, 'mog/problem/edit.html', {
                'form': form
            })
        data = form.cleaned_data
        problem = get_object_or_404(Problem, pk=problem_id)
        problem.title = data['title']
        problem.body = data['body']
        problem.input = data['input']
        problem.output = data['output']
        problem.hints = data['hints']
        problem.time_limit = data['time_limit']
        problem.memory_limit = data['memory_limit']
        problem.checker = data['checker']
        problem.position = data['position']
        problem.balloon = data['balloon']
        problem.letter_color = data['letter_color']
        problem.contest = data['contest']
        problem.tags = data['tags']
        problem.compilers = data['compilers']
        problem.save()
        return redirect('mog:problem', problem_id=problem.id, slug=problem.slug)


class ProblemListView(generic.ListView):
    paginate_by = 30
    template_name = 'mog/problem/index.html'

    def get_queryset(self):
        q, tag = self.request.GET.get('q'),\
                 self.request.GET.get('tag')

        tag = Tag.objects.filter(name=tag).first()

        if tag:
            problems = tag.get_visible_problems(user_is_admin(self.request.user))
        else:
            problems = Problem.get_visible_problems(user_is_admin(self.request.user))

        if q:
            problems = problems.filter(title__icontains=q)

        if not user_is_admin(self.request.user):
            problems = problems.filter(contest__start_date__lte=timezone.now())

        return problems.order_by('-contest__start_date', 'position')

    def get_context_data(self, **kwargs):
        context = super(ProblemListView, self).get_context_data(**kwargs)
        query = {}
        if 'q' in self.request.GET:
            query['q'] = self.request.GET['q']
        if 'tag' in self.request.GET:
            query['tag'] = self.request.GET['tag']
        context['query'] = query
        return context
