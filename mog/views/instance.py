from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import ContestInstance
from mog.gating import user_is_admin


@login_required
@require_http_methods(["GET"])
def instance_group_list(request):
    """Return the list of sorted group names used by previous instances.
    Filter group names by `q` parameter if exist.
    """
    if not user_is_admin(request.user):
        raise Http404()
    search = request.GET.get('q')
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
