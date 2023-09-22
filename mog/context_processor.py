from datetime import datetime

from django.contrib import messages
from django.urls import reverse

from api.lib import queries
from mog.utils import get_special_day


def common(request):
    # TODO(leandro): Think about this context processor and make sure
    # we don't compute unnecessary data to be sent to the template if
    # it will not be used at all. For instance, neither `top_rated_profiles`
    # nor `recent_modified_posts` are used in the problem detailed view.
    context = {
        "recent_modified_posts": queries.ten_most_recent_posts(),
        "top_rated_profiles": queries.five_top_rated_profiles(),
    }
    next = request.GET.get("next")
    if next:
        context["next"] = next
    if request.user.is_authenticated:
        context["unseen_messages"] = request.user.messages_received.filter(
            saw=False
        ).count()
    return context


def special_day(request):
    return {"special_day": get_special_day(datetime.now())}


def incomplete_profile(request):
    user = request.user
    if user.is_authenticated:
        profile = user.profile
        fields = [
            ("first name", user.first_name),
            ("last name", user.last_name),
            ("code theme", profile.theme),
            ("avatar", profile.avatar),
            ("institution", profile.institution),
            ("compiler", profile.compiler),
        ]
        incomplete = ", ".join([name for name, value in fields if not value])
        if incomplete:
            msg = (
                '<a href="%s">' % reverse("mog:user_edit", args=(user.id,))
                + "Please edit your profile and fill incomplete fields"
                + (" (%s)" % incomplete)
                + "</a>"
            )
            messages.info(request, msg, extra_tags="info secure")
    return {}
