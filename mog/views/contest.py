from django.core.urlresolvers import reverse

from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from api.models import Contest, ContestInstance, Team, Result, Compiler, RatingChange
from mog.forms import ContestForm
from mog.utils import user_is_admin, calculate_standing
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


def contest_registration(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    return render(request, 'mog/contest/registration.html', {
        'contest': contest
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
    problems, instance_results = calculate_standing(contest, show_virtual, user_instance)
    return render(request, 'mog/contest/standing.html', {
        'contest': contest,
        'instance_results': instance_results,
        'show_virtual': show_virtual,
        'user_instance': user_instance,
        'problems': problems
    })


@require_http_methods(["GET"])
def contest_submissions(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    submission_list, query = filter_submissions(
        request.user,
        problem=request.GET.get('problem'), contest=contest.id, username=request.GET.get('username'),
        result=request.GET.get('result'), compiler=request.GET.get('compiler')
    )
    submissions = get_paginator(submission_list, 30, request.GET.get('page'))
    return render(request, 'mog/contest/submissions.html', {
        'contest': contest,
        'submissions': submissions,
        'results': Result.get_all_results(),
        'compilers': Compiler.get_all_compilers(),
        'query': query
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


@login_required
@require_http_methods(["POST"])
def rate_contest(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    next = request.POST.get('next') or reverse('mog:contest_problems', args=(contest.id, ))
    force_rate = request.POST.get('force_rate', False)
    if contest.allow_teams:
        msg = _("This contest cannot be rated because it's open for teams.")
        messages.warning(request, msg, extra_tags='warning')
        return redirect(next)
    if not force_rate and contest.rated:
        msg = _("This contest have ben rated. If you want rate again, then force the operation.")
        messages.info(request, msg, extra_tags='info')
        return redirect(next)
    if RatingChange.objects\
            .filter(contest__rated=True, contest__start_date__gt=contest.start_date).count() > 0:
        msg = _("This contest cannot be rated because it's before a rated contest.")
        messages.success(request, msg, extra_tags='warning')
        return redirect(next)

    # remove previous rating changes
    contest.rating_changes.all().delete()

    # only instances with some problem solved will be rated
    __, instance_results = calculate_standing(contest)

    # remove instances that make not attempts in real contest
    # allow them participate virtually. keep users  with some
    # attempts.
    for ir in instance_results:
        if ir.attempts() == 0:
            ir.instance.delete()

    instance_results = [
        ir for ir in instance_results if ir.solved > 0
    ]

    ratings = []
    for ir in instance_results:
        profile = ir.instance.user.profile
        if profile.rating_changes.count() > 0:
            ratings.append(profile.rating)
        else:
            ratings.append(settings.BASE_RATING)

    expected = [0.5] * len(ratings)

    # TODO: review this three constants 10, 400, 32 (?)
    n = len(ratings)
    for i in range(n):
        for j in range(n):
            expected[i] += 1 / (1 + 10**((ratings[i] - ratings[j]) / 400.0))

    for i in range(n):
        # TODO: allow users go bellow than zero ?
        ir = instance_results[i]
        rating_delta = 32 * (expected[i] - ir.rank)
        if rating_delta < -settings.MAX_RATING_DELTA:
            rating_delta = -settings.MAX_RATING_DELTA
        if rating_delta > +settings.MAX_RATING_DELTA:
            rating_delta = +settings.MAX_RATING_DELTA
        RatingChange.objects.create(
            profile=ir.instance.user.profile,
            contest=contest,
            rating=rating_delta,
            rank=ir.rank
        )

    contest.rated = True
    contest.save()

    msg = _("This contest have been rated successfully")
    messages.success(request, msg, extra_tags='success')

    return redirect(next)


@login_required
@require_http_methods(["POST"])
def unrate_contest(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    next = request.POST.get('next') or reverse('mog:contest_problems', args=(contest.id, ))
    if RatingChange.objects\
            .filter(contest__rated=True, contest__start_date__gt=contest.start_date).count() > 0:
        msg = _("This contest cannot be unrated because it's before a rated contest")
        messages.warning(request, msg, extra_tags='warning')
        return redirect(next)
    contest.rating_changes.all().delete()
    contest.rated = False
    contest.save()
    msg = _("This contest have been unrated successfully")
    messages.success(request, msg, extra_tags='success')
    return redirect(next)
