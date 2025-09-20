from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
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

        institutions = (
            Institution.objects.select_related("country")
            .annotate(
                user_count=Count("userprofile", distinct=True),
                team_count=Count("team", distinct=True),
            )
            .order_by("name")
        )
        countries = Country.objects.all().order_by("name").only("id", "name")

        return render(
            request,
            "mog/institution/index.html",
            {"institutions": institutions, "countries": countries},
        )

    @method_decorator(login_required)
    def post(self, request, institution_id=None, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()

        # Handle institution deletion
        if institution_id and request.POST.get("_method") == "DELETE":
            return self.delete(request, institution_id, *args, **kwargs)

        # Handle institution creation (original POST logic)
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

    @method_decorator(login_required)
    def delete(self, request, institution_id, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden()

        try:
            institution = Institution.objects.get(pk=institution_id)
        except Institution.DoesNotExist:
            messages.error(request, _("Institution not found"), extra_tags="danger")
            return redirect(reverse("mog:institutions"))

        # Check if institution has users or teams
        user_count = institution.userprofile_set.count()
        team_count = institution.team_set.count()

        if user_count > 0 or team_count > 0:
            messages.error(
                request,
                _(
                    "Cannot delete institution with users or teams. Users: {}, Teams: {}"
                ).format(user_count, team_count),
                extra_tags="danger",
            )
            return redirect(reverse("mog:institutions"))

        try:
            institution.delete()
            messages.success(
                request, _("Institution deleted successfully"), extra_tags="success"
            )
        except Exception as e:
            messages.error(
                request, _("Error deleting institution: ") + str(e), extra_tags="danger"
            )

        return redirect(reverse("mog:institutions"))
