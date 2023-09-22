from django.db.models import Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View, generic
from django.views.decorators.http import require_http_methods

from api.models import Contest, Problem, Tag, Checker
from judge import settings
from mog.forms import ProblemForm
from mog.gating import is_admin_or_judge_for_problem, user_is_admin
from mog.samples import (
    get_tests,
    handle_remove_test,
    handle_tests,
    test_content,
)
from mog.model_helpers.contest import (
    can_create_problem_in_contest,
    get_all_contests_a_user_can_create_problems_in,
)


@login_required
@require_http_methods(["POST"])
def remove_problem(request, problem_id):
    problem = get_object_or_404(Problem, pk=problem_id)
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    problem.delete()
    msg = 'Problem "{0}" removed successfully!'.format(problem.title)
    messages.success(request, msg, extra_tags="success")
    return redirect("mog:contest_problems", contest_id=problem.contest_id)


@login_required
@require_http_methods(["POST"])
def remove_test(request, problem_id):
    problem = get_object_or_404(Problem, pk=problem_id)
    if not is_admin_or_judge_for_problem(request.user, problem):
        return HttpResponseForbidden()
    folder, test = request.POST.get("folder"), request.POST.get("test")
    if folder not in ["inputs", "outputs", "sample inputs", "sample outputs"]:
        msg = 'Invalid folder value, it mus be one of: "inputs", "outputs", "sample inputs", "sample outputs"'
        messages.success(request, msg, extra_tags="danger")
    elif not test:
        msg = "Test name not provided!"
        messages.success(request, msg, extra_tags="danger")
    else:
        msg = 'Test "%s/%s" removed successfully!' % (folder, test)
        messages.success(request, msg, extra_tags="success")
        handle_remove_test(problem, folder, test)
    return redirect("mog:problem_tests", problem_id=problem.id)


@login_required
def view_test(request, problem_id):
    problem = get_object_or_404(Problem, pk=problem_id)
    if not is_admin_or_judge_for_problem(request.user, problem):
        return HttpResponseForbidden()
    folder = request.GET.get("folder")
    test = request.GET.get("test")
    content = test_content(problem, folder, test)
    if not content:
        raise Http404()
    return render(
        request,
        "mog/test/view.html",
        {"folder": folder, "test": test, "problem": problem, "content": content},
    )


def problem(request, problem_id, slug):
    problem = get_object_or_404(Problem, pk=problem_id)
    if not problem.contest.can_be_seen_by(request.user):
        raise Http404()
    if problem.slug != slug:
        return redirect(
            "mog:problem", problem_id=problem_id, slug=problem.slug, permanent=True
        )
    si_folder, so_folder = "sample inputs", "sample outputs"
    si = [
        test_content(problem, si_folder, test) for test in get_tests(problem, si_folder)
    ]
    so = [
        test_content(problem, so_folder, test) for test in get_tests(problem, so_folder)
    ]
    return render(
        request, "mog/problem/detail.html", {"problem": problem, "samples": zip(si, so)}
    )


class ProblemTestsView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)
        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()
        if settings.DATA_SERVER_URL:
            return redirect(settings.DATA_SERVER_URL + request.path)
        return render(
            request,
            "mog/problem/tests.html",
            {
                "problem": problem,
                "sample_inputs": get_tests(problem, "sample inputs"),
                "sample_outputs": get_tests(problem, "sample outputs"),
                "inputs": get_tests(problem, "inputs"),
                "outputs": get_tests(problem, "outputs"),
            },
        )

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)
        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()
        handle_tests(problem, request.FILES.getlist("sample_inputs"), "sample inputs")
        handle_tests(problem, request.FILES.getlist("sample_outputs"), "sample outputs")
        handle_tests(problem, request.FILES.getlist("inputs"), "inputs")
        handle_tests(problem, request.FILES.getlist("outputs"), "outputs")
        return redirect("mog:problem_tests", problem_id=problem.id)


class ProblemEditView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)
        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()

        # NOTE(leandro): Get all contest ids that the current user has
        # access. Use a trick to convert to queryset from the contest
        # ids list that will be used in the form as choices for the
        # contest field.
        contest_ids = get_all_contests_a_user_can_create_problems_in(request.user)
        contests_queryset = Contest.objects.filter(pk__in=contest_ids)

        form = ProblemForm(instance=problem)
        form.fields["contest"].queryset = contests_queryset

        return render(
            request,
            "mog/problem/edit.html",
            {
                "form": form,
                "problem": problem,
            },
        )

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)
        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()

        form = ProblemForm(request.POST, instance=problem)
        if not form.is_valid():
            return render(
                request,
                "mog/problem/edit.html",
                {
                    "form": form,
                    "problem": problem,
                },
            )

        data = form.cleaned_data
        if not can_create_problem_in_contest(request.user, data["contest"]):
            return HttpResponseForbidden()

        problem.title = data["title"]
        problem.body = data["body"]
        problem.input = data["input"]
        problem.output = data["output"]
        problem.hints = data["hints"]
        problem.time_limit = data["time_limit"]
        problem.memory_limit = data["memory_limit"]
        problem.multiple_limits = data["multiple_limits"]
        problem.position = data["position"]
        problem.balloon = data["balloon"]
        problem.letter_color = data["letter_color"]
        problem.contest = data["contest"]
        problem.tags.set(data["tags"])
        problem.compilers.set(data["compilers"])
        problem.save()

        return redirect("mog:problem", problem_id=problem.id, slug=problem.slug)


class ProblemListView(generic.ListView):
    paginate_by = 30
    template_name = "mog/problem/index.html"

    def get_queryset(self):
        q, tag, sort_name, sort_mode = (
            self.request.GET.get("q"),
            self.request.GET.get("tag"),
            self.request.GET.get("sort"),
            self.request.GET.get("mode"),
        )

        tag = Tag.objects.filter(name=tag).first()

        if tag:
            problems = tag.get_visible_problems(user_is_admin(self.request.user))
        else:
            problems = Problem.get_visible_problems(user_is_admin(self.request.user))

        problems = problems.select_related("contest")

        if q:
            problems = problems.filter(title__icontains=q)

        sort_name = sort_name if sort_name in ["points"] else None

        order_by = []

        if sort_name:
            if sort_mode == "asc":
                order_by.append(sort_name)
            elif sort_mode == "desc":
                order_by.append("-" + sort_name)

        order_by.append("-contest__start_date")
        order_by.append("position")

        problems = problems.order_by(*order_by)

        if not user_is_admin(self.request.user):
            problems = problems.filter(contest__start_date__lte=timezone.now())

        return problems

    def get_context_data(self, **kwargs):
        context = super(ProblemListView, self).get_context_data(**kwargs)
        query = {}
        if "q" in self.request.GET:
            query["q"] = self.request.GET["q"]
        if "tag" in self.request.GET:
            query["tag"] = self.request.GET["tag"]

        sort = self.request.GET["sort"] if "sort" in self.request.GET else None
        mode = self.request.GET["mode"] if "mode" in self.request.GET else None

        if sort in ["points"] and mode in ["asc", "desc"]:
            query["sort"] = sort
            query["mode"] = mode

        context["query"] = query
        return context


class ProblemCheckerView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)
        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()

        checkers = Checker.objects.annotate(num_problems=Count("problem")).order_by(
            "-num_problems"
        )

        return render(
            request,
            "mog/problem/checker.html",
            {"problem": problem, "checkers": checkers},
        )

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)
        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()

        checker_id = request.POST.get("checker")
        checker = get_object_or_404(Checker, pk=int(checker_id))
        problem.checker = checker
        problem.save()

        return redirect("mog:problem", problem_id=problem.id, slug=problem.slug)
