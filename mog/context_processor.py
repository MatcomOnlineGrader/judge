from api.models import *


def common(request):
    context = {
        'recent_modified_posts': Post.objects.order_by('-modification_date')[:10],
        'top_rated_profiles': UserProfile.sorted_by_ratings()[:5]
    }
    next = request.GET.get('next')
    if next:
        context['next'] = next
    return context
