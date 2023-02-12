from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q

from api.models import Submission, Contest, Result, Compiler
from mog.gating import user_is_admin, get_all_contest_for_judge, is_admin_or_judge_or_observer_for_contest


def get_paginator(query_set, rows_per_page, current_page=1):
    paginator = Paginator(query_set, rows_per_page)
    try:
        items = paginator.page(current_page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)
    return items


def filter_submissions(user_who_request, problem=None, contest=None, username=None, result=None, compiler=None,
                       problem_exact=False, **kwargs):
    # The following section is the base line to further filtering of
    # submissions. Here, we select visible submissions only for
    # `user_who_request`.
    #
    # 1. If the user is an admin, there is nothing to filter. Admins
    # can see any submission.
    # 2. If the user is not admin, the idea is that they allways see
    # visible submissions ONLY (!hidden). However, judges are special
    # roles that can see hidden submissions of contest they have
    # granted access to. Thus, we should check for contests where the
    # user has role `judge` and include any submission of those
    # contests to the list (potentially hidden submissions).
    if user_is_admin(user_who_request):
        queryset = Submission.objects
    else:
        contest_ids = get_all_contest_for_judge(user_who_request)
        if contest_ids:
            queryset = Submission.objects.filter(Q(hidden=False) | (Q(hidden=True) & Q(problem__contest__in=contest_ids)))
        else:
            queryset = Submission.objects.filter(Q(hidden=False))

    query = {}
    if problem:
        if problem_exact:
            queryset = queryset.filter(problem__title=problem)
        else:
            # ignore case-sensitive
            queryset = queryset.filter(problem__title__icontains=problem)
        query['problem'] = problem  # no encode needed

    try:
        contest = Contest.objects.get(pk=contest)
        queryset = queryset.filter(problem__contest=contest)
        query['contest'] = str(contest.pk)  # encode back
    except (Contest.DoesNotExist, ValueError):
        contest = None

    if username:
        # by username and teamname
        queryset = queryset.filter(Q(user__username__icontains=username) | Q(instance__team__name__icontains=username))
        query['username'] = username  # no encode needed

    try:
        result = Result.objects.get(pk=result)
        if user_who_request.is_authenticated:
            if is_admin_or_judge_or_observer_for_contest(user_who_request, contest):
                queryset = queryset.filter(result=result)
            else:
                queryset = queryset.filter(
                    Q(result=result) & (Q(status='normal') | (Q(user=user_who_request) & Q(status='frozen')))
                )
        else:
            queryset = queryset.filter(result=result, status='normal')
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


def get_contest_json(contest, group=None):
    instances = contest.instances.filter(group=group, real=True) if group else contest.instances.filter(real=True)

    result = {"contestName": '%s - %s' % (contest.name, group) if group else contest.name,
              "freezeTimeMinutesFromStart": int(contest.duration.seconds / 60) - contest.frozen_time,
              "problemLetters": [x.letter for x in contest.get_problems],
              "contestants": [instance.team.name if instance.team is not None else instance.user.username
                              for instance in instances]}

    runs = []

    for instance in instances:
        for submission in instance.submissions.filter(Q(result__penalty=True) | Q(result__name__iexact=u'Accepted')):
            run = {"contestant": instance.team.name if instance.team is not None else instance.user.username,
                   "problemLetter": submission.problem.letter,
                   "timeMinutesFromStart": int((submission.date - contest.start_date).seconds / 60),
                   "success": submission.result.name == u'Accepted'}
            runs.append(run)

    runs.sort(key=lambda r: r["timeMinutesFromStart"])
    result["runs"] = runs
    return result