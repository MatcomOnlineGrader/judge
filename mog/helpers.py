from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

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
