import csv

from django.db.models.functions import Lower
from django.urls import reverse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as trans
from django.views import View
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from api.models import Contest, ContestInstance, Team, Result, Compiler, RatingChange, User, Q, Submission
from mog.forms import ContestForm, ClarificationForm
from mog.utils import user_is_admin, calculate_standing
from mog.helpers import filter_submissions, get_paginator

from mog.templatetags.filters import format_penalty, format_minutes


def contests(request):
    running, coming, past = Contest.get_all_contests(user_is_admin(request.user))
    return render(request, 'mog/contest/index.html', {
        'running_contests': running,
        'coming_contests': coming,
        'past_contests': past,
    })


def contest_clarifications(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    clarifications = contest.visible_clarifications(request.user)
    if request.user.is_authenticated:
        for clarification in clarifications:
            clarification.seen.add(request.user)
    return render(request, 'mog/contest/clarifications.html', {
        'contest': contest,
        'clarifications': clarifications,
        'form': ClarificationForm(contest=contest)
    })


def contest_problems(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    problems = contest.problems.order_by('position')
    return render(request, 'mog/contest/problems.html', {
        'contest': contest, 'problems': problems,
    })


@login_required
def contest_registration(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not user_is_admin(request.user):
        raise Http404()
    return render(request, 'mog/contest/registration.html', {
        'contest': contest,
        'instances': contest.instances.order_by(Lower('group')),
        'users': User.objects.all().order_by('username'),
        'teams': Team.objects.all().order_by('name')
    })


@require_http_methods(["GET"])
def contest_standing(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()

    user_instance = None
    if request.user.is_authenticated:
        user_instance = contest.instances.filter(user=request.user).first()
    show_virtual = request.GET.get('show_virtual') == 'on'

    group_in_ranking = request.GET.get('group', None)
    if group_in_ranking == '<all>':
        group_names = (contest.group_names() or [None])
    elif group_in_ranking == '<one>':
        group_names = [None]
    else:
        group_names = [group_in_ranking]

    # get ranking for every group
    ranking_groups = []
    for group in group_names:
        problems, instance_results = calculate_standing(
            contest,
            show_virtual,
            user_instance,
            group,
            user_is_admin(request.user)
        )
        ranking_groups.append({
            'group': group,
            'problems': problems,
            'instance_results': instance_results,
            'solved': sum(ir.solved for ir in instance_results),
            'penalty': sum(ir.penalty for ir in instance_results),
            'instances': len(instance_results)
        })
    return render(request, 'mog/contest/standing.html', {
        'contest': contest,
        'ranking_groups': ranking_groups,
        'show_virtual': show_virtual,
        'user_instance': user_instance,
        'group_names': contest.group_names(),
        'group_in_ranking': group_in_ranking
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


def register_instance(request, contest, user, team):
    """User in request is registering user/team"""

    nxt = request.POST.get('next')

    if not user_is_admin(request.user):
        if not contest.visible:
            # Admins are the only ones that can register user when
            # contest is hidden.
            raise Http404()

        if contest.closed:
            # Admins are the only ones that can register user when
            # registration is closed.
            msg = _(u'Registration is closed for contest "{0}"'.format(contest.name))
            messages.warning(request, msg, extra_tags='danger')
            return redirect(nxt or reverse('mog:contests'))

    # Check that no user has registered before.
    if team:
        users = [profile.user for profile in team.profiles.all()]
    elif user:
        users = [user]
    else:
        messages.error(request, _('No user to register'), extra_tags='error')
        return redirect(nxt or reverse('mog:contests'))

    # Check that user belongs to team
    if user and user not in users:
        messages.warning(request, _('Invalid user/team combination'), extra_tags='warning')
        return redirect(nxt or reverse('mog:contests'))

    # Check that the team can be registered in the contest
    if team and not contest.allow_teams:
        messages.warning(request, _("The contest doesn't allow teams"), extra_tags='warning')
        return redirect(nxt or reverse('mog:contests'))

    # Check that every user can register for real
    if all(contest.can_register_for_real(u) for u in users):
        real, start_date = True, None
    elif all(contest.can_register_for_virtual(u) for u in users):
        real, start_date = False, timezone.now()
    else:
        msg = _('Registration cannot be accomplished')
        messages.error(request, msg, extra_tags='danger')
        return redirect(nxt or reverse('mog:contests'))

    ContestInstance.objects.create(
        contest=contest,
        user=user,
        team=team,
        real=real,
        start_date=start_date,
        group=contest.group
    )

    if real:
        msg = _('Successfully registered for real participation')
    else:
        msg = _('Successfully registered for virtual participation')

    messages.success(request, msg, extra_tags='success')

    if real:
        return redirect(nxt or reverse('mog:contests'))

    return redirect(nxt or reverse('mog:contest_problems', args=(contest.pk, )))


@login_required
@require_http_methods(["POST"])
def contest_register(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    user = request.user
    try:
        team_id = int(request.POST.get('team'))
        team = get_object_or_404(Team, pk=team_id)
    except (ValueError, TypeError) as _:
        team = None
    return register_instance(request, contest, user, team)


@login_required
@require_http_methods(["POST"])
def contest_register_user(request, contest_id):
    """Administrative tool: Register user in contest"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    try:
        user_id = int(request.POST.get('user'))
    except (TypeError, ValueError):
        raise Http404()
    contest = get_object_or_404(Contest, pk=contest_id)
    user = get_object_or_404(User, pk=user_id)
    return register_instance(request, contest, user, None)


@login_required
@require_http_methods(["POST"])
def contest_register_team(request, contest_id):
    """Administrative tool: Register team in contest"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    try:
        team_id = int(request.POST.get('team'))
    except (TypeError, ValueError):
        raise Http404()
    contest = get_object_or_404(Contest, pk=contest_id)
    team = get_object_or_404(Team, pk=team_id)
    return register_instance(request, contest, None, team)


def remove_instance(request, instance):
    nxt = request.POST.get('next')

    if not instance:
        msg = _('Instance does not exist')
        messages.info(request, msg, extra_tags='info')
        return redirect(nxt or reverse('mog:contests'))

    if instance.submissions.count() > 0:
        msg = _('Cannot remove registration because the user/team has actions on the contest.')
        messages.warning(request, msg, extra_tags='warning')
        return redirect(nxt or reverse('mog:contests'))

    user = request.user

    if not user_is_admin(user):
        if instance.user != user and (instance.team and user.profile not in instance.team.profiles.all()):
            return HttpResponseForbidden()

    instance.delete()

    msg = _('Successfully unregistered!')
    messages.success(request, msg, extra_tags='success')

    return redirect(nxt or reverse('mog:contests'))


@login_required
@require_http_methods(["POST"])
def contest_remove_instance(request, instance_id):
    """
    This action is more flexible than `contest_remove_registration`
    and will be effectively used by admins, however, common users
    can post to this URL too removing only their own instances.
    """
    instance = ContestInstance.objects.filter(id=instance_id).first()
    return remove_instance(request, instance)


@login_required
@require_http_methods(["POST"])
def contest_remove_registration(request, contest_id):
    """
    Used by common users to remove their participation from a given
    contest without specify the target instance.
    """
    contest = get_object_or_404(Contest, pk=contest_id)
    instance = contest.registration(request.user)
    return remove_instance(request, instance)


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
            allow_teams=data['allow_teams'],
            group=data['group']
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
    next = request.POST.get('next') or reverse('mog:contest_problems', args=(contest.id,))
    force_rate = request.POST.get('force_rate', False)
    if contest.allow_teams:
        msg = _("This contest cannot be rated because it's open for teams.")
        messages.warning(request, msg, extra_tags='warning')
        return redirect(next)
    if not force_rate and contest.rated:
        msg = _("This contest have ben rated. If you want rate again, then force the operation.")
        messages.info(request, msg, extra_tags='info')
        return redirect(next)
    if RatingChange.objects \
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

    ratings, before = [], []
    for ir in instance_results:
        profile = ir.instance.user.profile
        if profile.rating_changes.count() > 0:
            before.append(True)
            ratings.append(profile.rating)
        else:
            before.append(False)
            ratings.append(settings.BASE_RATING)

    expected = [0.5] * len(ratings)

    # TODO: review this three constants 10, 400, 32 (?)
    n = len(ratings)
    for i in range(n):
        for j in range(n):
            expected[i] += 1 / (1 + 10 ** ((ratings[i] - ratings[j]) / 400.0))

    for i in range(n):
        ir = instance_results[i]
        rating_delta = int(32 * (expected[i] - ir.rank))
        if rating_delta < -settings.MAX_RATING_DELTA:
            rating_delta = -settings.MAX_RATING_DELTA
        if rating_delta > +settings.MAX_RATING_DELTA:
            rating_delta = +settings.MAX_RATING_DELTA
        if not before[i]:
            rating_delta += ratings[i]
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
    next = request.POST.get('next') or reverse('mog:contest_problems', args=(contest.id,))
    if RatingChange.objects \
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


@login_required
@require_http_methods(["POST"])
def unfreeze_contest(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    updated = Submission.objects.filter(Q(problem__contest=contest) & ~Q(status='normal'))\
        .update(status='normal')
    msg = '%s %d %s' % (_("Contest unfrozen successfully"), updated, _('submission(s) affected'))
    messages.success(request, msg, extra_tags='success')
    return redirect(reverse('mog:contest_problems', args=(contest.id,)))


@login_required
def contest_json(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)

    result = {"contestName": contest.name,
              "freezeTimeMinutesFromStart": int(contest.duration.seconds / 60) - contest.frozen_time,
              "problemLetters": [x.letter for x in contest.get_problems],
              "contestants": [instance.team.name if instance.team is not None else instance.user.username
                              for instance in contest.instances.all()]}

    runs = []
    append = runs.append

    # TODO: See Next Line!!!
    # for instance in contest.instances.filter(real=True):
    for instance in contest.instances.all():
        for submission in instance.submissions.filter(Q(result__penalty=True) | Q(result__name__iexact=u'Accepted')):
            run = {"contestant": instance.team.name if instance.team is not None else instance.user.username,
                   "problemLetter": submission.problem.letter,
                   "timeMinutesFromStart": int((submission.date - contest.start_date).seconds / 60),
                   "success": submission.result.name == u'Accepted'}
            append(run)

    runs.sort(key=lambda r: r["timeMinutesFromStart"])
    result["runs"] = runs

    return JsonResponse(data=result)


@login_required
def contest_csv(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()

    contest = get_object_or_404(Contest, pk=contest_id)
    problems, instance_results = calculate_standing(contest, True, None)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{0}.csv"'.format(contest.name.encode('utf-8').strip())

    response.write("sep=,\r\n")

    writerow = csv.writer(response).writerow

    header = [trans('Rank'), trans('Team'), trans('Solved'), trans('Penalty')]
    header.extend([problem.letter for problem in problems])
    writerow(map(lambda x: x.encode('utf-8'), header))

    append = list.append

    for instance_result in instance_results:
        instance = instance_result.instance
        row = []

        append(row, instance_result.rank)
        name = '' if instance.real else '(~) '

        if instance.team is not None:
            name += instance.team.name.encode('utf-8').strip()
            if instance.team.institution is not None:
                name += ' ({0})'.format(instance.team.institution.name.encode('utf-8').strip())
        else:
            name += instance.user.username.encode('utf-8').strip()
            if instance.user.profile.institution is not None:
                name += ' ({0})'.format(instance.user.profile.institution.name.encode('utf-8').strip())

        append(row, name)
        append(row, instance_result.solved)
        append(row, format_penalty(instance_result.penalty))

        for problem_result in instance_result.problem_results:
            cell = ''
            if problem_result.accepted:
                cell = format_minutes(problem_result.acc_delta)
            if problem_result.attempts > 0:
                cell += ' (-{0})'.format(problem_result.attempts)
            append(row, cell.strip())
        writerow(row)

    return response
