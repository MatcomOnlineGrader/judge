from django.db.models import Count
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views import View

from api.models import Problem, Checker
from mog.gating import is_admin_or_judge_for_problem, user_is_admin


class CheckerView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)

        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()

        return render(request, "mog/checker/create.html", {"problem": problem})

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)

        name = request.POST.get("name")
        description = request.POST.get("description")
        source = request.POST.get("source")
        file_source = request.FILES.get("file")
        backend = request.POST.get("backend")

        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()

        if file_source is not None:
            source = file_source.read().decode("utf8")

        if not source:
            msg = _("Empty source code")
            messages.info(request, msg, extra_tags="info")
            return redirect("mog:checker", problem_id=problem.id)

        if Checker.objects.filter(name=name).exists():
            msg = _('Name "%s" already exists' % name)
            messages.warning(request, msg, extra_tags="warning")
            return redirect("mog:checker", problem_id=problem.id)

        try:
            checker = Checker(
                name=name,
                description=description,
                source=source,
                backend=backend,
            )
            checker.save()
        except Exception as e:
            msg = _("Error creating a new checker: " + str(e))
            messages.error(request, msg, extra_tags="danger")
            return redirect("mog:checker", problem_id=problem.id)

        return redirect("mog:problem_checker", problem_id=problem.id)


@login_required
def view_checker(request):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()

    checkers = Checker.objects.annotate(num_problems=Count("problem")).order_by(
        "-num_problems"
    )

    return render(request, "mog/checker/view_checker.html", {"checkers": checkers})


class CreateCheckerView(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        return render(request, "mog/checker/create_checker.html")

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()

        name = request.POST.get("name")
        description = request.POST.get("description")
        source = request.POST.get("source")
        file_source = request.FILES.get("file")
        backend = request.POST.get("backend")

        if file_source is not None:
            source = file_source.read().decode("utf8")

        if not source:
            msg = _("Empty source code")
            messages.info(request, msg, extra_tags="info")
            return redirect("mog:create_checker")

        if Checker.objects.filter(name=name).exists():
            msg = _('Name "%s" already exists' % name)
            messages.warning(request, msg, extra_tags="warning")
            return redirect("mog:create_checker")

        try:
            checker = Checker(
                name=name,
                description=description,
                source=source,
                backend=backend,
            )
            checker.save()
        except Exception as e:
            msg = _("Error creating a new checker: " + str(e))
            messages.error(request, msg, extra_tags="danger")
            return redirect("mog:create_checker")

        return redirect("mog:view_checker")
