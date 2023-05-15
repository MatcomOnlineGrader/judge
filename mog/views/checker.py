from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django.views.static import serve

from api.models import Problem, Checker
from judge import settings
from mog.gating import is_admin_or_judge_for_problem, is_admin_or_judge

import os


class CheckerView(View):
    @method_decorator(login_required)
    def get(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)

        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()

        return render(request, 'mog/checker/create.html', {
            'problem': problem
        })

    @method_decorator(login_required)
    def post(self, request, problem_id, *args, **kwargs):
        problem = get_object_or_404(Problem, pk=problem_id)

        name = request.POST.get('name')
        description = request.POST.get('description')
        source = request.POST.get('source')
        file_source = request.FILES.get('file')
        backend = request.POST.get('backend')
        
        if not is_admin_or_judge_for_problem(request.user, problem):
            return HttpResponseForbidden()
        
        if file_source is not None:
            source = file_source.read().decode('utf8')

        if not source:
            msg = _(u'Empty source code')
            messages.info(request, msg, extra_tags='info')
            return redirect('mog:checker', problem_id=problem.id)
        
        if Checker.objects.get(name=name):
            msg = _(u'Name "%s" already exists' % name)
            messages.warning(request, msg, extra_tags='warning')
            return redirect('mog:checker', problem_id=problem.id)

        try:
            checker = Checker(
                name=name,
                description=description,
                source=source,
                backend=backend,
            )
            checker.save()
        except Exception as e:
            msg = _('Error creating a new checker: ' + str(e))
            messages.error(request, msg, extra_tags='danger')
            return redirect('mog:checker', problem_id=problem.id)

        return redirect('mog:problem_checker', problem_id=problem.id)


@login_required
def exports_checker_testlib(request):
    file_name = request.GET.get('file', '')
    file_path = os.path.join(settings.BASE_DIR, 'resources', file_name)
    
    if not is_admin_or_judge(request.user):
        return HttpResponseForbidden()

    if os.path.exists(file_path):
        try:
            response = serve(request, os.path.basename(file_path), os.path.dirname(file_path))
            response['Content-Disposition'] = 'attachment; filename="{}"'.format(file_name)
            return response
        except:
            pass
    else:
        return HttpResponse('File not found', status=404)
