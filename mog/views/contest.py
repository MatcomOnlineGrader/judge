import io
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
from django.utils.timesince import timesince
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
    ContestPermission
)
from mog.decorators import public_actions_required

from mog.forms import (
    ContestForm,
    ClarificationForm,
    ProblemInContestForm,
    ImportBaylorForm,
    ImportGuestTeamsForm,
    ImportPermissionForm
)
from mog.gating import user_is_admin, user_can_bypass_frozen_in_contest, user_is_judge_in_contest, grant_role_to_user_in_contest, revoke_role_to_user_in_contest
from mog.helpers import filter_submissions, get_paginator, get_contest_json
from mog.ratings import get_rating_deltas, check_rating_deltas, set_ratings
from mog.statistics import get_contest_stats
from mog.templatetags.filters import format_minutes, rating_color, user_color
from mog.templatetags.security import can_manage_contest
from mog.model_helpers.contest import can_create_problem_in_contest
from mog.samples import fix_problem_folder

from mog.baylor.import_baylor import ProcessImportBaylor
from mog.baylor.import_team import ProcessImportTeam
from mog.baylor.team_password import ZipTeamPassword
from mog.baylor.utils import ICPCID_GUEST_PREFIX, CSV_PERMISSION_HEADER

from .permissions import set_granted_to_permission
from .submission import get_submission


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


@login_required
def contest_manage(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not can_manage_contest(request.user, contest):
        return HttpResponseForbidden()
    
    if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
        msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
        messages.warning(request, msg, extra_tags='warning secure')

    return render(request, 'mog/contest/manage.html', {
        'contest': contest,
        'form_import_baylor': ImportBaylorForm(),
        'form_import_guest': ImportGuestTeamsForm(),
    })


@login_required
@require_http_methods(["POST"])
def contest_manage_import_baylor(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not can_manage_contest(request.user, contest):
        return HttpResponseForbidden()

    if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
        msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
        messages.warning(request, msg, extra_tags='warning secure')

    form_import_baylor = ImportBaylorForm(request.POST, request.FILES)

    zip_baylor = None
    prefix_baylor = None
    select_pending_teams_baylor = False

    if form_import_baylor.is_valid():
        data = form_import_baylor.cleaned_data
        zip_baylor = data['zip_baylor']
        prefix_baylor = data['prefix_baylor']
        select_pending_teams_baylor = data['select_pending_teams_baylor']

        if zip_baylor and prefix_baylor:
            try:
                with zipfile.ZipFile(zip_baylor, 'r') as zip_ref:
                    process_baylor_file = ProcessImportBaylor(zip_ref, contest_id, prefix_baylor, select_pending_teams_baylor)
                    results = process_baylor_file.handle()
                    for result in results:
                        if result['type'] == 'success':
                            messages.success(request, result['message'], extra_tags='success secure')
                        else: 
                            messages.warning(request, result['message'], extra_tags='warning secure')
            except Exception as e:
                msg = _('Error reading file from baylor: ' + str(e))
                messages.error(request, msg, extra_tags='danger')
    
    return redirect('mog:contest_manage', contest_id=contest.id)


@login_required
@require_http_methods(["POST"])
def contest_manage_import_guest(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not can_manage_contest(request.user, contest):
        return HttpResponseForbidden()

    form_import_guest = ImportGuestTeamsForm(request.POST, request.FILES)
    csv_teams = None
    prefix_team = None

    if form_import_guest.is_valid():
        data = form_import_guest.cleaned_data
        csv_teams = data['csv_teams']
        prefix_team = data['prefix_team']

        if csv_teams and prefix_team:
            try:
                csv_ref = csv_teams.read().decode('utf-8').splitlines()
                process_guest_team = ProcessImportTeam(csv_ref, contest_id, prefix_team)
                results = process_guest_team.handle()
                for result in results:
                    if result['type'] == 'success':
                        messages.success(request, result['message'], extra_tags='success secure')
                    else: 
                        messages.warning(request, result['message'], extra_tags='warning secure')
            except Exception as e:
                msg = _('Error reading CSV Guest Teams file: ' + str(e))
                messages.error(request, msg, extra_tags='danger')

    return redirect('mog:contest_manage', contest_id=contest.id)


@login_required
@require_http_methods(["GET"])
def contest_manage_export_password(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not can_manage_contest(request.user, contest):
        return HttpResponseForbidden()
    
    zip_team_password = ZipTeamPassword(contest)
    zip_passwords = zip_team_password.generate_zip_team_password()
    response = HttpResponse(zip_passwords, content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="passwords_{0}.zip"'.format(contest.name)
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
        'instances': contest.instances.order_by(Lower('group'), 'team__institution__name', 'team__name')
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
        group_names = (contest.group_names(include_virtual=show_virtual) or [None])
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
        'group_names': contest.group_names(include_virtual=show_virtual),
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
    compilers_id = list({compiler_id['compilers'] for compiler_id in list(contest.problems.values('compilers'))})
    compilers = Compiler.objects.filter(pk__in=compilers_id).order_by('name')
    return render(request, 'mog/contest/submissions.html', {
        'contest': contest,
        'submissions': submissions,
        'results': Result.get_all_results(),
        'compilers': compilers,
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
def contest_registration_multiple_register_user(request, contest_id):
    """Administrative tool: Register users in contest"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    group = request.POST.get('user-group', '').strip()
    members = request.POST.get('user-members', '').split(',')
    users = []

    if group in ['<all>', '<one>']:
        messages.error(request, 'Invalid group name "%s"' % group, extra_tags='danger')
        return redirect(reverse('mog:contest_registration', args=(contest.pk, )))

    try:
        for member in members:
            users.append(get_object_or_404(User, pk=int(member)))
        users = set(users)
        count = 0
        for user in users:
            if ContestInstance.objects.filter(contest=contest, user=user).first():
                messages.warning(request, _("User '%s' is already registerd" % user.username), extra_tags='warning')
                continue

            if ContestInstance.objects.filter(Q(contest_id=contest.id), Q(team__profiles__user_id=user.id)):
                messages.warning(request, _('The user "%s" is already registered as a team!' % user.username), extra_tags='warning')
                continue

            ContestInstance.objects.create(
                contest=contest,
                user=user,
                real=True,
                group=group or contest.group
            )
            count += 1
        msg = _('Successfully registered ' + str(count) + ' new user')
        messages.success(request, msg, extra_tags='success')
        
    except (ValueError, TypeError):
        messages.error(request, 'Register users: Invalid data!', extra_tags='danger')

    return redirect(reverse('mog:contest_registration', args=(contest.pk, )))


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


@login_required
@require_http_methods(["POST"])
def contest_registration_multiple_register_team(request, contest_id):
    """Administrative tool: Register teams in contest"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    group = request.POST.get('team-group', '').strip()
    members = request.POST.get('team-members', '').split(',')
    teams = []

    if group in ['<all>', '<one>']:
        messages.error(request, 'Invalid group name "%s"' % group, extra_tags='danger')
        return redirect(reverse('mog:contest_registration', args=(contest.pk, )))

    try:
        for member in members:
            teams.append(get_object_or_404(Team, pk=int(member)))
        teams = set(teams)
        count = 0
        for team in teams:
            # Check that the team can be registered in the contest
            if not contest.allow_teams:
                messages.warning(request, _("The contest doesn't allow teams"), extra_tags='warning')
                return redirect(reverse('mog:contests'))
            
            if ContestInstance.objects.filter(contest=contest, team__name=team.name).exists():
                messages.warning(request, _('There is a team registered with the same name "%s", please check it out, register skiped!' % team.name), extra_tags='warning')
                continue
            
            if ContestInstance.objects.filter(contest=contest, team=team).first():
                messages.warning(request, _("Team '%s' is already registerd" % team.name), extra_tags='warning')
                continue

            # team > profiles > [user_id]
            profiles = [profile.user.id for profile in team.profiles.all()]
            if ContestInstance.objects.filter(Q(contest_id=contest.id), Q(user_id__in=profiles) | Q(team__profiles__user_id__in=profiles)):
                messages.warning(request, _('There are an user within the team "%s" that is already registered with another team or as an user, please check it out, register skiped!' % team.name), extra_tags='warning')
                continue
            
            ContestInstance.objects.create(
                contest=contest,
                team=team,
                real=True,
                group=group or contest.group
            )
            count += 1
        msg = _('Successfully registered ' + str(count) + ' new team')
        messages.success(request, msg, extra_tags='success')
        
    except (ValueError, TypeError):
        messages.error(request, 'Register teams: Invalid data!', extra_tags='danger')

    return redirect(reverse('mog:contest_registration', args=(contest.pk, )))


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


@login_required
@require_http_methods(["POST"])
def contest_registration_multiple_unregister(request, contest_id):
    """Administrative tool: Remove registration for multiple user/team"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()

    contest = get_object_or_404(Contest, pk=contest_id)
    nxt = request.POST.get('next') or reverse('mog:contest_registration', args=(contest.pk, ))
    instances_selected = request.POST.get('instances-unregister-selected', '').split(',')
    instances = []
    
    try:
        for selected in instances_selected:
            instances.append(get_object_or_404(ContestInstance, pk=int(selected)))
        instances=set(instances)
        count = 0
        for instance in instances:
            if not instance:
                continue
            if instance.team:
                team = True
                name = instance.team.name
            else:
                team = False
                name = instance.user.username
            if instance.submissions.count() > 0:
                msg = _("Cannot remove registration of '%s' because the %s has actions on the contest." % (name, 'team' if team else 'user'))
                messages.warning(request, msg, extra_tags='warning')
                continue
            instance.delete()
            count += 1
        msg = _("Successfully unregistered %d user/team!" % count)
        messages.success(request, msg, extra_tags='success')

    except (ValueError, TypeError):
        messages.error(request, 'Unregister user/team: Invalid data!', extra_tags='danger')

    return redirect(nxt)


def set_contest_registration_multiple_enable(request, contest_id, instances_selected, is_active):
    """Administrative tool: Enable multiple instance users from contest"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    nxt = request.POST.get('next') or reverse('mog:contest_registration', args=(contest.pk, ))
    instances = []
    
    try:
        count = 0
        for selected in instances_selected:
            instances.append(get_object_or_404(ContestInstance, pk=int(selected)))
        instances=set(instances)
        for instance in instances:
            if instance.is_active != is_active:
                instance.is_active = is_active
                instance.save()
                count += 1

        msg = _("Successfully %s %d users" % ('enable' if is_active else 'disable', count))
        messages.success(request, msg, extra_tags='success')

    except (ValueError, TypeError):
        messages.error(request, 'Enable/disable users: Invalid data!', extra_tags='danger')

    return redirect(nxt)


@login_required
@require_http_methods(["POST"])
def contest_registration_multiple_enable(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    instances_selected = request.POST.get('instances-enable-selected', '').split(',')
    return set_contest_registration_multiple_enable(request, contest_id, instances_selected, True)


@login_required
@require_http_methods(["POST"])
def contest_registration_multiple_disable(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    instances_selected = request.POST.get('instances-disable-selected', '').split(',')
    return set_contest_registration_multiple_enable(request, contest_id, instances_selected, False)


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
    response['Content-Disposition'] = 'attachment; filename="{0}.csv"'.format(contest.name.strip())

    response.write("sep=,\r\n")

    writerow = csv.writer(response).writerow

    header = [trans('Rank'), trans('Team'), trans('Solved'), trans('Penalty')]
    header.extend([problem.letter for problem in problems])
    writerow(map(lambda x: x, header))

    append = list.append

    for instance_result in instance_results:
        instance = instance_result.instance
        row = []

        append(row, instance_result.rank)
        name = '' if instance.real else '(~) '

        if instance.team is not None:
            name += instance.team.name.strip()
            if instance.team.institution is not None:
                name += ' ({0})'.format(instance.team.institution.name.strip())
        else:
            name += instance.user.username.strip()
            if instance.user.profile.institution is not None:
                name += ' ({0})'.format(instance.user.profile.institution.name.strip())

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
    response['Content-Disposition'] = 'attachment; filename="standing_{0}.csv"'.format(contest.name)

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
        if instance.team.icpcid.startswith(ICPCID_GUEST_PREFIX):
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
            is_html=False,
        )
        problem.save()
        problem.tags.set(data['tags'])
        problem.compilers.set(data['compilers'])
        fix_problem_folder(problem)
        return redirect('mog:problem', problem_id=problem.id, slug=problem.slug)


@login_required
@require_http_methods(["GET"])
def contest_instances_info(request, contest_id):
    if not user_is_admin(request.user):
        raise Http404()
    contest = get_object_or_404(Contest, pk=contest_id)
    instances = contest.instances.order_by(Lower('group'))
    instances_data = {}
    for instance in instances:
        if instance.team:
            team = instance.team
            last_login = None
            list_profiles = []
            for profile in team.profiles.all():
                list_profiles.append({
                    'id': profile.user.id,
                    'username': profile.user.username,
                    'rating_color': rating_color(profile.rating)
                })
                l = profile.user.last_login
                if last_login is None:
                    last_login = l
                elif l is not None:
                    last_login = max(last_login, l)
            instances_data[instance.pk] = {
                'team': {
                    'name': team.name,
                    'last_login': timesince(last_login) if last_login else None,
                    'profiles': list_profiles,
                },
            }
        elif instance.user:
            user = instance.user
            instances_data[instance.pk] = {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'last_login': timesince(user.last_login) if user.last_login else None,
                    'rating_color': user_color(user),
                },
            }
    return JsonResponse(data={
        'success': True,
        'data': instances_data
    })


@login_required
def contest_permission(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not can_manage_contest(request.user, contest):
        return HttpResponseForbidden()
    
    if user_is_admin(request.user) and contest.needs_unfreeze and contest.is_past:
        msg = _('This contest is still frozen. Go to <b>Actions -> Unfreeze contest </b> to see the final results!')
        messages.warning(request, msg, extra_tags='warning secure')

    return render(request, 'mog/contest/permission.html', {
        'contest': contest,
        'permissions': ContestPermission.objects.filter(contest=contest).order_by('-granted', 'role', 'user__username'),
        'form_import_permission': ImportPermissionForm()
    })


@login_required
@require_http_methods(["POST"])
def contest_add_permission(request, contest_id):
    """Administrative tool: Add persission to user in contest"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    
    contest = get_object_or_404(Contest, pk=contest_id)
    
    next = request.POST.get('next') or reverse('mog:contest_permission', args=(contest.pk, ))
    observer = request.POST.get('observer', '')
    judge = request.POST.get('judge', '')
    members = request.POST.get('user-members', '').split(',')
    users = []

    if not observer and not judge:
        msg = _('You need to assign at least one permission (observer / judge) to the users.')
        messages.success(request, msg, extra_tags='warning')
        return redirect(next)

    try:
        for member in members:
            users.append(get_object_or_404(User, pk=int(member)))
        users = set(users)
        
        for user in users:
            if judge:
                prev_permission = ContestPermission.objects.filter(contest=contest, user=user, role='judge').first()
                if prev_permission:
                    set_granted_to_permission(prev_permission, True)
                else:
                    grant_role_to_user_in_contest(user, contest, role='judge')
            if observer:
                prev_permission = ContestPermission.objects.filter(contest=contest, user=user, role='observer').first()
                if prev_permission:
                    set_granted_to_permission(prev_permission, True)
                else:
                    grant_role_to_user_in_contest(user, contest, role='observer')
        msg = _('Successfully assigned ' + str(len(users)) + ' new users roles.')
        messages.success(request, msg, extra_tags='success')
        
    except (ValueError, TypeError):
        messages.error(request, 'Permission users: Invalid data!', extra_tags='danger')

    return redirect(next)


@login_required
def contest_permission_export(request, contest_id):
    if not user_is_admin(request.user):
        return HttpResponseForbidden()

    contest = get_object_or_404(Contest, pk=contest_id)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="permission_{0}.csv"'.format(contest.name)

    writer = csv.writer(response)

    header = ['username',
              'role',
              'granted']
    writer.writerow(header)

    permissions = ContestPermission.objects.filter(contest=contest)

    for permission in permissions:
        row = [permission.user.username,
               permission.role,
               permission.granted]
        writer.writerow(row)

    return response


@login_required
@require_http_methods(["POST"])
def contest_permission_import(request, contest_id):
    contest = get_object_or_404(Contest, pk=contest_id)

    if not can_manage_contest(request.user, contest):
        return HttpResponseForbidden()

    form_import_permission = ImportPermissionForm(request.POST, request.FILES)

    csv_permission = None
    
    if form_import_permission.is_valid():
        data = form_import_permission.cleaned_data
        csv_permission = data['csv_permission']

        if csv_permission:
            try:
                csv_ref = csv_permission.read().decode('utf-8').splitlines()
                reader = list(csv.reader(csv_ref))

                if ','.join(reader[0]).strip() != CSV_PERMISSION_HEADER:
                    raise Exception('CSV file header must be %s' % CSV_PERMISSION_HEADER)
                
                for line in reader[1:]:
                    user = User.objects.filter(username=str(line[0])).first()
                    if not user:
                        msg = _('Username ' + str(line[0]) + ' do not exists.')
                        messages.success(request, msg, extra_tags='warning')
                        continue
                    role = line[1].lower()
                    granted = line[2].lower() == 'true'
                    prev_permission = ContestPermission.objects.filter(contest=contest, user=user, role=role).first()
                    if prev_permission:
                        set_granted_to_permission(prev_permission, granted)
                    elif granted:
                        grant_role_to_user_in_contest(user, contest, role)
                    else:
                        revoke_role_to_user_in_contest(user, contest, role)
                    
                msg = _('Successfully assigned ' + str(len(reader) - 1) + ' new users roles.')
                messages.success(request, msg, extra_tags='success')

            except Exception as e:
                msg = _('Error reading CSV User Permissions file: ' + str(e))
                messages.error(request, msg, extra_tags='danger')

    return redirect('mog:contest_permission', contest_id=contest.id)


@login_required
@require_http_methods(["POST"])
def contest_registration_multiple_edit_group(request, contest_id):
    """Administrative tool: Edit group for multiple user/team"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()

    contest = get_object_or_404(Contest, pk=contest_id)
    nxt = request.POST.get('next') or reverse('mog:contest_registration', args=(contest.pk, ))
    group = request.POST.get('instances-group', '').strip()
    instances_selected = request.POST.get('instances-group-selected', '').split(',')
    instances = []

    if group in ['<all>', '<one>']:
        messages.error(request, 'Invalid group name "%s"' % group, extra_tags='danger')
        return redirect(nxt)
    
    try:
        for selected in instances_selected:
            instances.append(get_object_or_404(ContestInstance, pk=int(selected)))
        instances=set(instances)
        count = 0
        for instance in instances:
            if not instance:
                continue
            instance.group = group or contest.group
            instance.save()
            count += 1
        msg = _("Successfully moved %d user/team to Group '%s'" % (count, group))
        messages.success(request, msg, extra_tags='success')

    except (ValueError, TypeError):
        messages.error(request, 'Unregister user/team: Invalid data!', extra_tags='danger')

    return redirect(nxt)


@require_http_methods(['GET'])
def contest_submissions_export(request, contest_id):
    """Export ZIP with all submission of a contest"""
    if not user_is_admin(request.user):
        return HttpResponseForbidden()
    contest = get_object_or_404(Contest, pk=contest_id)
    instances_id = contest.instances.values_list('id')
    problems = contest.get_problems

    try:
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w') as zipObj:
            for problem in problems:
                header = 'submissions_%s/%s' % (contest.name, problem.letter)
                submissions = Submission.objects.filter(problem_id=problem.id, instance_id__in=instances_id)
                for submission in submissions:
                    filename, source = get_submission(submission)
                    zipObj.writestr('%s/%s' % (header, filename), source)
        zip_submissions = content.getvalue()
        response = HttpResponse(zip_submissions, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="submissions_{0}.zip"'.format(contest.name)
        return response
    
    except Exception as e:
        msg = _('Error exporting submissions: ' + str(e))
        messages.error(request, msg, extra_tags='danger')
        return HttpResponseForbidden()
