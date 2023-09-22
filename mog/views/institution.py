from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_http_methods

from api.models import Institution
from mog.gating import user_is_admin


@login_required
@require_http_methods(["GET"])
def institution_list(request):
    """Return the list of sorted institution names.
    Filter institution names by `q` parameter if exist.
    """
    if not user_is_admin(request.user):
        raise Http404()
    q = request.GET.get("q", "")
    institutions_list = (
        Institution.objects.filter(Q(name__icontains=q) | Q(country__name__icontains=q))
        .order_by("name")
        .values("id", "name")
    )
    return JsonResponse(data={"success": True, "data": list(institutions_list)})
