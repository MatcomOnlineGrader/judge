import csv
import json
import zipfile

from django.db.models.functions import Lower
from django.urls import reverse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as trans
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django.views.decorators.http import require_http_methods

from api.lib.queries import calculate_standing
from api.models import (
    Compiler,
    Contest,
    ContestInstance,
    Problem,
    RatingChange,
    Result,
    Submission,
    Team,
    User,
)
from mog.decorators import public_actions_required

from mog.forms import ContestForm, ClarificationForm, ProblemInContestForm
from mog.gating import user_is_admin, user_can_bypass_frozen_in_contest, user_is_judge_in_contest
from mog.helpers import filter_submissions, get_paginator, get_contest_json
from mog.ratings import get_rating_deltas, check_rating_deltas, set_ratings
from mog.statistics import get_contest_stats
from mog.templatetags.filters import format_minutes
from mog.model_helpers.contest import can_create_problem_in_contest
from mog.samples import fix_problem_folder

from mog.import_baylor import ProcessImportBaylor
from mog.forms import ImportBaylorForm, ExportBaylorForm
from mog.templatetags.security import can_manage_baylor

def contests(request):
    running, coming, past = \
        Contest.get_all_contests(request.user)
    return render(request, 'mog/contest/index.html', {
        'running_contests': running,
        'coming_contests': coming,
        'past_contests': past,
    })


def contest_clarifications(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()

    if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
        msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
        messages.warning(request, msg, extra_tags='warning secure')

    clarifications = contest.visible_clarifications(request.user)

    if request.user.is_authenticated:
        for clarification in clarifications:
            clarification.seen.add(request.user)
    return render(request, 'mog/contest/clarifications.html', {
        'contest': contest,
        'clarifications': clarifications,
        'form': ClarificationForm(contest=contest)
    })


def contest_overview(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not contest.overview_can_be_seen_by(request.user):
        raise Http404()

    if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
        msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
        messages.warning(request, msg, extra_tags='warning secure')

    return render(request, 'mog/contest/overview.html', {
        'contest': contest,
    })


def contest_problems(request, contest_id):
    contest, user = get_object_or_404(Contest, pk=contest_id), \
        request.user

    if not contest.can_be_seen_by(user):
        return redirect(reverse('mog:contest_overview', args=(contest.pk, )))

    if user_is_admin(user) and contest.needs_unfreeze and contest.is_past:
        msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
        messages.warning(request, msg, extra_tags='warning secure')

    return render(request, 'mog/contest/problems.html', {
        'contest': contest,
        'problems': contest.problems.order_by('position'),
        'can_create_problem': can_create_problem_in_contest(user, contest)
    })


manage_baylor_url = 'mog/contest/manage_baylor.html'

class ManageBaylorView(View):
    @method_decorator(login_required)
    def get(self, request, contest_id, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=contest_id)

        if not can_manage_baylor(request.user, contest):
            return HttpResponseForbidden()
        
        if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
            msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
            messages.warning(request, msg, extra_tags='warning secure')

        return render(request, manage_baylor_url, {
            'contest': contest,
            'form_import': ImportBaylorForm(),
            'form_export': ExportBaylorForm(contest=contest)
        })

    @method_decorator(login_required)
    def post(self, request, contest_id, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=contest_id)

        if not can_manage_baylor(request.user, contest):
            return HttpResponseForbidden()

        if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
            msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
            messages.warning(request, msg, extra_tags='warning secure')

        form_import = ImportBaylorForm(request.POST, request.FILES)
        form_export = ExportBaylorForm(contest=contest, data=request.POST)

        zip_baylor = None
        prefix_baylor = None
        select_pending_teams_baylor = False
        remove_teams_baylor = False

        site_citation_selected = None

        if form_import.is_valid():
            data = form_import.cleaned_data
            zip_baylor = data['zip_baylor']
            prefix_baylor = data['prefix_baylor']
            select_pending_teams_baylor = data['select_pending_teams_baylor']
            remove_teams_baylor = data['remove_teams_baylor']

            if zip_baylor and prefix_baylor:
                # try:
                with zipfile.ZipFile(zip_baylor, 'r') as zip_ref:
                    process_baylor_file = ProcessImportBaylor(zip_ref, contest_id, prefix_baylor, select_pending_teams_baylor, remove_teams_baylor)
                    result = process_baylor_file.handle()
                    messages.success(request, result, extra_tags='success')
                    zip_passwords = process_baylor_file.generate_zip_password(contest.name)
                    response = HttpResponse(zip_passwords, content_type='application/zip')
                    response['Content-Disposition'] = 'attachment; filename="passwords_{0}.zip"'.format(contest.name)
                    return response
                # except Exception as e:
                #     msg = _('Error reading file from baylor: ' + str(e))
                #     messages.error(request, msg, extra_tags='danger')
        
        elif form_export.is_valid():
            data = form_export.cleaned_data
            site_citation_selected = data['site_citation']
            response = get_baylor_csv(contest, site_citation_selected)
            return response

        return render(request, manage_baylor_url, { 
            'contest': contest,
            'form_import': ImportBaylorForm(),
            'form_export': form_export
        })


def get_baylor_csv(contest, site_citation):
    
    problems, instance_results = calculate_standing(contest, False, None)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="standings_{0}.csv"'.format(contest.name)

    writer = csv.writer(response)

    header = ['teamId',
            'rank',
            'medalCitation',
            'problemsSolved',
            'totalTime',
            'lastProblemTime',
            'siteCitation',
            'citation']
    writer.writerow(header)

    rank = 0
    last_rank = 0
    for instance_result in instance_results:
        instance = instance_result.instance
        if not instance.team or not instance.team.icpcid or instance.group == contest.group:
            continue
        if instance.group not in site_citation:
            continue

        if instance_result.rank != last_rank:
            rank += 1
        last_rank = instance_result.rank

        row = [instance.team.icpcid,
            rank,
            '',
            instance_result.solved,
            instance_result.penalty,
            int(instance_result.last_accepted_delta)//60,
            instance.group,
            'Rank %d' % rank]

        writer.writerow(row)

    return response


@login_required
def contest_registration(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not user_is_admin(request.user):
        raise Http404()

    if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
        msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
        messages.warning(request, msg, extra_tags='warning secure')

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
        user_instance = contest.registration(request.user)

    if contest.is_running:
        show_virtual = False
        show_virtual_checkbox = False
    elif user_instance and user_instance.is_running:
        show_virtual = not user_instance.real
        show_virtual_checkbox = False
    else:
        show_virtual = request.GET.get('show_virtual') == 'on'
        show_virtual_checkbox = True

    group_in_ranking = request.GET.get('group', None)
    if not group_in_ranking and user_instance and not user_instance.real:
        # by default in virtual participation show all teams in one group
        group_names = [None]
    elif group_in_ranking == '<all>':
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
            user_can_bypass_frozen_in_contest(request.user, contest)
        )
        ranking_groups.append({
            'group': group,
            'problems': problems,
            'instance_results': instance_results,
            'solved': sum(ir.solved for ir in instance_results),
            'penalty': sum(ir.penalty for ir in instance_results),
            'instances': len(instance_results)
        })

        def key(group):
            if user_instance and group['group'] == user_instance.group:
                return -1e9, 0
            if group['group'] == contest.group:
                return 1e6, 0
            return -group['solved'], group['penalty']
        ranking_groups = sorted(ranking_groups, key=key)

    return render(request, 'mog/contest/standing.html', {
        'contest': contest,
        'ranking_groups': ranking_groups,
        'show_virtual': show_virtual,
        'user_instance': user_instance,
        'group_names': contest.group_names(),
        'group_in_ranking': group_in_ranking,
        'show_virtual_checkbox': show_virtual_checkbox
    })


@require_http_methods(["GET"])
def contest_submissions(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    if not contest.can_be_seen_by(request.user):
        raise Http404()
    submission_list, query = filter_submissions(
        request.user,
        problem=request.GET.get('problem'),
        problem_exact=True,
        contest=contest.id,
        username=request.GET.get('username'),
        result=request.GET.get('result'),
        compiler=request.GET.get('compiler')
    )
    submissions = get_paginator(submission_list, 30, request.GET.get('page'))
    return render(request, 'mog/contest/submissions.html', {
        'contest': contest,
        'submissions': submissions,
        'results': Result.get_all_results(),
        'compilers': Compiler.get_all_compilers(),
        'query': query
    })


@require_http_methods(["GET"])
def contest_rating_changes(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not contest.is_past or not contest.rated:
        raise Http404()

    return render(request, 'mog/contest/rating_changes.html', {
        'contest': contest,
        'rating_changes': contest.rating_changes.all().order_by('rank')
    })


@require_http_methods(["GET"])
def team_submissions(request, contest_id, team_id):
    contest = get_object_or_404(Contest, pk=contest_id)
    team = get_object_or_404(Team, pk=team_id)

    if not contest.can_be_seen_by(request.user):
        raise Http404()

    profile = team.profiles.first()

    if not profile:
        raise Http404()

    return redirect(reverse('mog:contest_submissions', args=(contest_id,))+'?username='+profile.user.username)


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
def register_instance(request, contest, user, team):
    """User in request is registering user/team"""

    nxt = request.POST.get('next')

    if not user_is_admin(request.user):
        if not contest.visible:
            # Admins are the only ones that can register user when
            # contest is hidden.
            raise Http404()

        if contest.closed and not contest.is_past:
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

    bypass_closed = user_is_admin(request.user)
    # Check that every user can register for real
    if all(contest.can_register_for_real(u, bypass_closed) for u in users):
        real, start_date = True, None
    elif all(contest.can_register_for_virtual(u) for u in users):
        real, start_date = False, timezone.now()
    else:
        msg = _('Registration cannot be accomplished, some of the team members cannot participate')
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


@public_actions_required
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

    if instance.contest.closed and not user_is_admin(user):
        msg = _('Cannot remove registration because the contest is closed.')
        messages.warning(request, msg, extra_tags='warning')
        return redirect(nxt or reverse('mog:contests'))

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


@public_actions_required
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
        contest = get_object_or_404(Contest, pk=contest_id)

        if not user_is_admin(request.user):
            return HttpResponseForbidden()

        return render(request, 'mog/contest/edit.html', {
            'form': ContestForm(instance=contest), 'contest': contest,
        })

    @method_decorator(login_required)
    def post(self, request, contest_id, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=contest_id)

        if not user_is_admin(request.user):
            return HttpResponseForbidden()

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
def contest_saris(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not contest.can_show_saris_to(request.user):
        return HttpResponseForbidden()

    group = request.POST.get('group', None)

    result = get_contest_json(contest, group)

    return render(request, 'mog/contest/saris.html', {
        'contest': contest, 'json': json.dumps(result)
    })


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

    if set_ratings(contest):
        msg = _("This contest has been rated successfully")
        messages.success(request, msg, extra_tags='success')
    else:
        msg = _("The rating-changes results are not consistent")
        messages.info(request, msg, extra_tags='info')

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

    if contest.is_past:
        updated = Submission.objects.filter(Q(problem__contest=contest) & ~Q(status='normal')) \
            .update(status='normal')
        contest.needs_unfreeze = False
        contest.save()
        msg = '%s %d %s' % (_("Contest unfrozen successfully"), updated, _('submission(s) affected'))
        messages.success(request, msg, extra_tags='success')
    else:
        msg = _("Contest couldn't be unfrozen because it is coming or running!")
        messages.warning(request, msg, extra_tags='warning')

    return redirect(reverse('mog:contest_problems', args=(contest.id,)))


@login_required
def contest_stats(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()

    contest = get_object_or_404(Contest, pk=contest_id)
    result = get_contest_stats(contest)

    return JsonResponse(data=result, safe=False)


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
        append(row, instance_result.penalty)

        for problem_result in instance_result.problem_results:
            cell = ''
            if problem_result.accepted:
                cell = format_minutes(problem_result.acc_delta)
            if problem_result.attempts > 0:
                cell += ' (-{0})'.format(problem_result.attempts)
            append(row, cell.strip())
        writerow(row)

    return response


@login_required
def contest_baylor(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()

    contest = get_object_or_404(Contest, pk=contest_id)
    problems, instance_results = calculate_standing(contest, False, None)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{0}.csv"'.format(contest.name)

    writer = csv.writer(response)

    header = ['teamId',
              'rank',
              'medalCitation',
              'problemsSolved',
              'totalTime',
              'lastProblemTime',
              'siteCitation',
              'citation']
    writer.writerow(header)

    rank = 0
    last_rank = 0
    for instance_result in instance_results:
        instance = instance_result.instance
        if not instance.team or not instance.team.icpcid or instance.group == contest.group:
            continue

        if instance_result.rank != last_rank:
            rank += 1
        last_rank = instance_result.rank

        row = [instance.team.icpcid,
               rank,
               '',
               instance_result.solved,
               instance_result.penalty,
               int(instance_result.last_accepted_delta)//60,
               instance.group,
               'Rank %d' % rank]

        writer.writerow(row)

    return response


class CreateProblemInContestView(View):
    @method_decorator(login_required)
    def get(self, request, contest_id, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=contest_id)
        if not can_create_problem_in_contest(request.user, contest):
            raise Http404()
        return render(request, 'mog/contest/create_problem.html', {
            'form': ProblemInContestForm(), 'contest': contest
        })

    @method_decorator(login_required)
    def post(self, request, contest_id, *args, **kwargs):
        contest = get_object_or_404(Contest, pk=contest_id)
        if not can_create_problem_in_contest(request.user, contest):
            raise Http404()
        form = ProblemInContestForm(request.POST)
        if not form.is_valid():
            return render(request, 'mog/contest/create_problem.html', {
                'form': form, 'contest': contest
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
            multiple_limits=data['multiple_limits'],
            checker=data['checker'],
            position=data['position'],
            balloon=data['balloon'],
            letter_color=data['letter_color'],
            contest=contest,
        )
        problem.save()
        problem.tags.set(data['tags'])
        problem.compilers.set(data['compilers'])
        fix_problem_folder(problem)
        return redirect('mog:problem', problem_id=problem.id, slug=problem.slug)
