from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import ContestInstance, Institution
from mog.gating import user_is_admin


@login_required
@require_http_methods(["GET"])
def instance_group_list(request):
    """Return the list of sorted group names used by previous instances.
    Filter group names by `q` parameter if exist.
    """
    if not user_is_admin(request.user):
        raise Http404()
    search = request.GET.get('q', '')
    groups_list = ContestInstance.objects.filter(~Q(group=None), group__icontains=search)\
        .order_by('group').values_list('group', flat=True).distinct()
    return JsonResponse(data={
        'success': True,
        'data': list(groups_list)
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def instance_edit_group(request, instance_pk):
    """Set `group` name to instance"""
    if not user_is_admin(request.user):
        raise Http404()
    try:
        group = request.POST.get('group', '').strip()
        if group in ['<all>', '<one>']:
            return JsonResponse(data={
                'success': False,
                'message': 'Invalid group name "%s"' % group
            })
        ContestInstance.objects.filter(pk=instance_pk)\
            .update(group=(group or None))
    except:
        return JsonResponse(data={
            'success': False,
            'message': 'Contest instance not found'
        })
    return JsonResponse(data={
        'success': True
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def instance_edit_render_description(request, instance_pk):
    """Set flag render_team_description_only"""
    if not user_is_admin(request.user):
        raise Http404()

    instance = get_object_or_404(ContestInstance, pk=instance_pk)
    check = request.POST.get('render_team_description_only', '') == 'on'
    instance.render_team_description_only = check
    instance.save()

    return redirect('mog:contest_registration', contest_id=instance.contest_id)


@login_required
@require_http_methods(["POST"])
def instance_edit_team(request, instance_pk):
    """Set description and institution of team"""
    if not user_is_admin(request.user):
        raise Http404()

    instance = get_object_or_404(ContestInstance, pk=instance_pk)

    nxt = request.POST.get('nxt', '') or reverse('mog:contest_registration', args=(instance.contest.pk, ))
    description = request.POST.get('description', '')
    institution_id = request.POST.get('institution', '')

    try:
        institution = Institution.objects.filter(id=int(institution_id)).first()
        if not institution:
            raise Exception('Institution with id=%s not exist' % institution_id)

        if instance.team.institution_id != institution.id:
            instance.team.institution = institution

        if instance.team.description != description:
            instance.team.description = description

        instance.team.save()

        msg = _("Successfully edited Team '%s'" % instance.team.name)
        messages.success(request, msg, extra_tags='success')

    except (ValueError, TypeError):
        messages.error(request, 'Edit team: Invalid data!', extra_tags='danger')

    return redirect(nxt)
