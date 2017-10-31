from datetime import datetime

from django.contrib import messages

from api.models import *


def common(request):
    recent_modified_posts = Post.objects.order_by('-modification_date')\
        .select_related('user').select_related('user__profile')
    top_rated_profiles = UserProfile.sorted_by_ratings()\
        .select_related('user')
    context = {
        'recent_modified_posts': recent_modified_posts[:10],
        'top_rated_profiles': top_rated_profiles[:5]
    }
    next = request.GET.get('next')
    if next:
        context['next'] = next
    if request.user.is_authenticated():
        context['unseen_messages'] = request.user\
            .messages_received.filter(saw=False).count()
    return context


def special_days(request):
    now = datetime.now()
    day = 'regular'
    if now.month == 2 and now.day == 14:
        day = 'valentine'
    if now.month == 12 and 19 <= now.day <= 31:
        day = 'christmas'
    if now.month == 10 and now.day == 31:
        day = 'halloween'
    return {
        'special_day': day
    }


def incomplete_profile(request):
    user = request.user
    if user.is_authenticated:
        profile = user.profile
        fields = [
            ('first name', user.first_name),
            ('last name', user.last_name),
            ('code theme', profile.theme),
            ('avatar', profile.avatar),
            ('institution', profile.institution),
            ('compiler', profile.compiler),
        ]
        incomplete = ', '.join([name for name, value in fields if not value])
        if incomplete:
            msg = '<a href="%s">' % reverse('mog:user_edit', args=(user.id, ))\
                  + 'Please edit your profile and fill incomplete fields'\
                  + (' (%s)' % incomplete)\
                  + '</a>'
            messages.info(request, msg, extra_tags='info secure')
    return {}
