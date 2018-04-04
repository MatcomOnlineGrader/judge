from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from api.models import User, Team, Submission, Institution
from mog.utils import user_is_admin


@login_required
@require_http_methods(["POST"])
def create_team(request):
    main_user = request.POST.get('main_user')
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    members = request.POST.get('members', '').split(',')
    users = []

    try:
        main_user = get_object_or_404(User, pk=int(main_user))
        users.append(main_user)
        for member in members:
            users.append(get_object_or_404(User, pk=int(member)))
        users = set(users)
    except (ValueError, TypeError):
        messages.success(request, 'Create Team: Invalid data!', extra_tags='danger')
        return redirect('mog:index')

    try:
        institution = None
        if request.POST.get('institution'):
            institution = Institution.objects.get(pk=request.POST.get('institution'))
    except:
        messages.success(request, 'Create Team: Invalid institution!', extra_tags='danger')
        redirect('mog:user_teams', user_id=main_user.id)

    if not user_is_admin(request.user) and request.user != main_user:
        messages.success(request, 'Create Team: Permission denied!', extra_tags='danger')
        return redirect('mog:index')

    if len(name) == 0:
        messages.success(request, 'Create Team: Name cannot be empty!', extra_tags='danger')
        return redirect('mog:index')

    team = Team.objects.create(
        name=name,
        description=description,
        institution=institution
    )

    for user in users:
        team.profiles.add(user.profile)

    messages.success(request, 'Team "%s" created successfully!' % name, extra_tags='success')

    return redirect('mog:user_teams', user_id=main_user.id)


@login_required
@require_http_methods(["POST"])
def remove_team(request, team_id):
    try:
        main_user = get_object_or_404(User, pk=int(request.POST.get('main_user')))
    except (ValueError, TypeError):
        messages.success(request, 'Remove Team: Invalid main user!', extra_tags='danger')
        return redirect('mog:index')

    team = get_object_or_404(Team, pk=team_id)
    users = [profile.user.id for profile in team.profiles.all()]

    if not user_is_admin(request.user) and request.user.id not in users:
        messages.success(request, 'Remove Team: Permission denied!', extra_tags='danger')
        return redirect('mog:index')

    if Submission.objects.filter(instance__team=team).count() > 0:
        msg = 'Team "%s" cannot be removed because it has submissions!' % team.name
        messages.success(request, msg, extra_tags='warning')
    else:
        team.delete()
        msg = 'Team "%s" removed successfully!' % team.name
        messages.success(request, msg, extra_tags='success')

    return redirect('mog:user_teams', user_id=main_user.id)
