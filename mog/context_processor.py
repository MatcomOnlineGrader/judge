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
