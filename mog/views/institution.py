from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext_lazy as _
from django.views import View
from django.views.decorators.http import require_http_methods

from api.models import Institution, Country
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


class InstitutionListView(View):
    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()

        institutions = Institution.objects.select_related("country").order_by("name")
        countries = Country.objects.all().order_by("name").only("id", "name")

        return render(
            request,
            "mog/institution/index.html",
            {"institutions": institutions, "countries": countries},
        )

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()

        name = request.POST.get("name", "").strip()
        url = request.POST.get("url", "").strip()
        country_id = request.POST.get("country")

        if not name:
            messages.warning(request, _("Name is required"), extra_tags="warning")
            return redirect(reverse("mog:institutions"))

        country = None
        if country_id:
            try:
                country = Country.objects.get(pk=country_id)
            except Country.DoesNotExist:
                messages.warning(request, _("Invalid country"), extra_tags="warning")
                return redirect(reverse("mog:institutions"))

        try:
            inst = Institution(name=name, url=url or None, country=country)
            inst.save()
        except Exception as e:
            messages.error(
                request, _("Error creating institution: ") + str(e), extra_tags="danger"
            )
            return redirect(reverse("mog:institutions"))

        messages.success(request, _("Institution created"), extra_tags="success")
        return redirect(reverse("mog:institutions"))
