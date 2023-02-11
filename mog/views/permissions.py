from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api.models import ContestPermission
from mog.gating import user_is_admin


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def contest_permission_edit_granted(request, permission_pk):
    """Set flag granted"""
    if not user_is_admin(request.user):
        raise Http404()

    permission = get_object_or_404(ContestPermission, pk=permission_pk)
    granted = request.POST.get('granted', '') == 'on'
    set_granted_to_permission(permission, granted)

    return redirect('mog:contest_permission', contest_id=permission.contest_id)


def set_granted_to_permission(permission, granted):
    permission.granted = granted
    permission.save()