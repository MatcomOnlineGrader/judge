import os
import shutil
import subprocess
import uuid

from django.template.loader import get_template
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.template.context import Context
from django.conf import settings

from mog.utils import test_content, get_tests

from api.models import Submission, Contest, Result, Compiler


def get_paginator(query_set, rows_per_page, current_page=1):
    paginator = Paginator(query_set, rows_per_page)
    try:
        items = paginator.page(current_page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)
    return items


def filter_submissions(user_who_request, problem=None, contest=None, username=None, result=None, compiler=None, **kwargs):
    query = {}
    queryset = Submission.visible_submissions(user_who_request)

    if problem:
        queryset = queryset.filter(problem__title__contains=problem)
        query['problem'] = problem  # no encode needed

    try:
        contest = Contest.objects.get(pk=contest)
        queryset = queryset.filter(problem__contest=contest)
        query['contest'] = str(contest.pk)  # encode back
    except (Contest.DoesNotExist, ValueError):
        contest = None

    if username:
        queryset = queryset.filter(user__username__icontains=username)
        query['username'] = username  # no encode needed

    try:
        result = Result.objects.get(pk=result)
        queryset = queryset.filter(result=result)
        query['result'] = str(result.pk)  # encode back
    except (Result.DoesNotExist, ValueError):
        result = None

    try:
        compiler = Compiler.objects.get(pk=compiler)
        queryset = queryset.filter(compiler=compiler)
        query['compiler'] = str(compiler.pk)  # encode back
    except (Compiler.DoesNotExist, ValueError):
        compiler = None

    return queryset.order_by('-pk'), query


# import django
# django.setup()
# from api.models import *
# from mog.helpers import problem2pdf
# for problem in Problem.objects.order_by('id'):
#     print problem.id, 'OK' if problem2pdf(problem) else 'ERROR'
def problem2pdf(problem):
    si_folder, so_folder = 'sample inputs', 'sample outputs'
    si = [test_content(problem, si_folder, test) for test in get_tests(problem, si_folder)]
    so = [test_content(problem, so_folder, test) for test in get_tests(problem, so_folder)]
    template = get_template('mog/latex/problem.html')
    context = Context({'problem': problem, 'samples': zip(si, so)})
    content = template.render(context).encode('utf-8')

    path = os.path.join(settings.MEDIA_ROOT, 'problem', 'pdf', str(problem.id))
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

    problem_html = '%d.html' % problem.id
    problem_tex = '%d.tex' % problem.id
    problem_pdf = '%d.pdf' % problem.id

    html_path = os.path.join(path, problem_html)
    with open(html_path, 'w') as f:
        f.write(content)

    pandoc = subprocess.Popen(
        ['pandoc', '-f', 'html+tex_math_dollars+tex_math_single_backslash', '-s', '--mathjax',
         problem_html, '-o', problem_tex], cwd=path,
        stderr=subprocess.PIPE, stdout=subprocess.PIPE
    )

    pandoc.wait()

    if os.path.exists(os.path.join(path, problem_tex)):
        pdflatex = subprocess.Popen(
            ['pdflatex', '-halt-on-error', problem_tex], cwd=path,
            stderr=subprocess.PIPE, stdout=subprocess.PIPE
        )
        pdflatex.wait()

    # Remove all files others than problem_pdf
    for filename in os.listdir(path):
        if filename != problem_pdf:
            os.remove(os.path.join(path, filename))

    return os.path.exists(os.path.join(path, '%d.pdf' % problem.id))
