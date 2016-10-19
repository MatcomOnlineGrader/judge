from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from api.models import Contest, ContestInstance, Team
from mog.forms import ContestForm
from mog.utils import user_is_admin
from mog.helpers import filter_submissions, get_paginator


def contests(request):
    running, coming, past = Contest.get_all_contests(user_is_admin(request.user))
    return render(request, 'mog/contest/index.html', {
        'running_contests': running,
        'coming_contests': coming,
        'past_contests': past,
    })


def contest_problems(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    problems = contest.problems.order_by('position')
    return render(request, 'mog/contest/problems.html', {
        'contest': contest, 'problems': problems,
    })


@require_http_methods(["GET"])
def contest_standing(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not contest.can_be_seen_by(request.user):
        raise Http404()

    user_instance = None
    if request.user.is_authenticated():
        user_instance = contest.virtual_registration(request.user)

    show_virtual = request.GET.get('show_virtual') == 'on'

    instances = contest.instances if show_virtual else \
        contest.instances.filter(real=True)

    instances = instances.select_related('team', 'user').all()

    problems = contest.problems.order_by('position').all()

    context = {
        'instances': [],
        'contest': contest,
        'problems': problems,
        'show_virtual': show_virtual,
        'instance': user_instance
    }

    for instance in instances:
        i = {
            'problems': [],
            'user': instance.user,
            'team': instance.team,
            'solved': 0,
            'penalty': 0,
            'real': instance.real
        }
        penalty, solved = 0, 0
        for problem in problems:
            accepted = instance.get_submissions(problem, user_instance)\
                .filter(result__name__iexact='accepted').order_by('date').first()
            if accepted:
                attempts = instance.get_submissions(problem, user_instance) \
                    .filter(result__penalty=True, date__lt=accepted.date).count()
            else:
                attempts = instance.get_submissions(problem, user_instance) \
                    .filter(result__penalty=True).count()
            acc_delta = None
            if accepted:
                if instance.real:
                    acc_delta = accepted.date - contest.start_date
                else:
                    acc_delta = accepted.date - instance.start_date
                penalty += acc_delta.total_seconds() / 60 + 20 * attempts
                solved += 1
            i['problems'].append({
                'accepted': accepted is not None,
                'acc_delta': acc_delta,
                'attempts': attempts,
                'first': False,
            })
        i['solved'] = solved
        i['penalty'] = penalty
        context['instances'].append(i)

    contest_first_solved_problem = None
    contest_first_solved_instance = None
    contest_first_solved_time = None

    for i in range(len(problems)):
        problem_first_solved_instance = None
        problem_first_solved_time = None
        for j in range(len(instances)):
            instance = context['instances'][j]
            if instance['problems'][i]['accepted']:
                acc_delta = instance['problems'][i]['acc_delta']
                if problem_first_solved_instance is None or problem_first_solved_time > acc_delta:
                    problem_first_solved_time = acc_delta
                    problem_first_solved_instance = j
        if problem_first_solved_instance is not None:
            context['instances'][problem_first_solved_instance]['problems'][i]['first'] = True
            if contest_first_solved_instance is None or \
                            contest_first_solved_time > problem_first_solved_time:
                contest_first_solved_problem = i
                contest_first_solved_instance = problem_first_solved_instance
                contest_first_solved_time = problem_first_solved_time

    if contest_first_solved_instance is not None:
        instance = context['instances'][contest_first_solved_instance]
        problem = instance['problems'][contest_first_solved_problem]
        problem['contest_first_solved'] = True

    context['instances'] = sorted(context['instances'],
        key=lambda inst: (-inst['solved'], inst['penalty'] or float("inf")))

    previous, rank = None, 1
    for instance in context['instances']:
        if previous is not None and \
                (instance['solved'] != previous['solved'] or instance['penalty'] != previous['penalty']):
            rank += 1
        instance['rank'] = rank
        previous = instance

    return render(request, 'mog/contest/standing.html', context)


@require_http_methods(["GET"])
def contest_submissions(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    submission_list, query = filter_submissions(
        request.user,
        problem=request.GET.get('problem'), contest=contest.id, user=request.GET.get('user'),
        result=request.GET.get('result'), compiler=request.GET.get('compiler')
    )
    submissions = get_paginator(submission_list, 30, request.GET.get('page'))
    return render(request, 'mog/contest/submissions.html', {
        'contest': contest, 'submissions': submissions, 'query': query
    })


@login_required
@require_http_methods(["POST"])
def remove_contest(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    contest.delete()
    msg = u'Contest "{0}" removed successfully!'.format(contest.name)
    messages.success(request, msg, extra_tags='success')
    return redirect('mog:contests')


@login_required
@require_http_methods(["POST"])
def contest_register(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    start_date, real, team = None, False, None

    if contest.allow_teams:
        team_id = request.POST.get('team')
        if team_id is not None and team_id.isdigit():
            team = get_object_or_404(Team, pk=int(team_id))

    if contest.can_register_for_real(request.user):
        real = True
    elif contest.can_register_for_virtual(request.user):
        start_date = timezone.now()
    else:
        messages.success(request, 'You cannot register in this contest', extra_tags='success')
        return redirect('mog:contests')

    ContestInstance.objects.create(
        user=request.user, contest=contest,
        real=real, team=team, start_date=start_date
    )

    if real:
        msg = u'Successfully registered for real participation in "{0}"!'.format(contest.name)
        messages.success(request, msg, extra_tags='success')
        return redirect('mog:contests')

    return redirect('mog:contest_problems', contest_id=contest.id)


@login_required
@require_http_methods(["POST"])
def contest_unregister(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    instances = contest.instances\
        .filter(Q(user=request.user) | Q(team__in=request.user.profile.teams.all())).all()

    if instances.count() == 0:
        msg = u'You are not register in this contest!'
        messages.success(request, msg, extra_tags='info')
        return redirect('mog:contests')

    if instances.count() > 1:
        # TODO: Bad things here!
        pass

    errors = False
    for instance in instances:
        if instance.submissions.count() == 0:
            instance.delete()
        else:
            errors = True

    if errors:
        msg = u'You cannot unregister from this contest because you have some actions on it!'
        messages.success(request, msg, extra_tags='warning')
    else:
        msg = u'Successfully unregistered!'
        messages.success(request, msg, extra_tags='success')

    return redirect('mog:contests')


class ContestCreateView(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        return render(request, 'mog/contest/create.html', {
            'form': ContestForm()
        })

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        form = ContestForm(request.POST)
        if not form.is_valid():
            return render(request, 'mog/contest/create.html', {
                'form': form
            })
        data = form.cleaned_data
        contest = Contest(
            name=data['name'],
            code=data['code'],
            description=data['description'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            visible=data['visible'],
            frozen_time=data['frozen_time'],
            death_time=data['death_time'],
            closed=data['closed'],
            allow_teams=data['allow_teams']
        )
        contest.save()
        return redirect('mog:contest_problems', contest_id=contest.id)


class ContestEditView(View):
    @method_decorator(login_required)
    def get(self, request, contest_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        contest = get_object_or_404(Contest, pk=contest_id)
        return render(request, 'mog/contest/edit.html', {
            'form': ContestForm(instance=contest), 'contest': contest,
        })

    @method_decorator(login_required)
    def post(self, request, contest_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()
        contest = get_object_or_404(Contest, pk=contest_id)
        form = ContestForm(request.POST, instance=contest)
        if not form.is_valid():
            return render(request, 'mog/contest/edit.html', {
                'form': form, 'contest': contest,
            })
        data = form.cleaned_data
        contest.name = data['name']
        contest.code = data['code']
        contest.description = data['description']
        contest.start_date = data['start_date']
        contest.end_date = data['end_date']
        contest.visible = data['visible']
        contest.frozen_time = data['frozen_time']
        contest.death_time = data['death_time']
        contest.closed = data['closed']
        contest.allow_teams = data['allow_teams']
        contest.save()
        return redirect('mog:contest_problems', contest_id=contest.id)
