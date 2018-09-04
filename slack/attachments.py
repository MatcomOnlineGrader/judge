from django.db.models import Count

from api.models import Contest, Comment, Message, Post,\
    Problem, Submission, User, UserProfile
from mog.templatetags.filters import get_color
from slack.charts import google_pie
from slack.utils import CachedResult


STATS_KEY = 'slack:stats'

RANK_KEY = 'slack:rank'

RESULT_COLORS = {
    'Accepted': '007E33',
    'Compilation Error': '0099CC',
    'Compiling': '00695C',
    'Disqualified': '9933CC',
    'Idleness Limit Exceeded': '1C2331',
    'Internal Error': '3E2723',
    'Memory Limit Exceeded': 'FFD600',
    'Pending': 'FF8800',
    'Running': 'FF4444',
    'Runtime Error': '33B5E5',
    'Time Limit Exceeded': '4B515D',
    'Wrong Answer': 'CC0000',
}

DIVISION_COLORS = {
    'blue': '#0000FF',
    'gray': '#808080',
    'green': '#00FF00',
    'orange': '#FF8000',
    'purple': '#800080',
    'red': '#FF0000',
    'black': '#000000'
}


@CachedResult(key=STATS_KEY, timeout=30)
def get_statistics():
    results = Submission.objects.filter(hidden=False)\
            .values('result__name', 'result__color').order_by('result__name').annotate(result__count=Count('*'))
    attachments = []
    attachments.append({
        'text': '\n'.join(
            ['*%s*: %s' % (result['result__name'], result['result__count']) for result in results]
        ),
        'image_url': google_pie(
            [result['result__name'] for result in results],
            [result['result__count'] for result in results],
            colors=[RESULT_COLORS[result['result__name']] for result in results]
        )
    })
    attachments.append({
        'text': '\n'.join([
            '*Contests*: %d' % Contest.objects.filter(visible=True).count(),
            '*Submissions*: %d' % Submission.objects.filter(hidden=False).count(),
            '*Users*: %d (%d active)' % (User.objects.count(), User.objects.filter(is_active=True).count()),
            '*Posts*: %d' % Post.objects.count(),
            '*Problems*: %d' % Problem.objects.filter(contest__visible=True).count(),
            '*Comments* (posts): %d' % Comment.objects.count(),
            '*Messages* (users): %d' % Message.objects.count(),
        ])
    })
    return attachments


@CachedResult(key=RANK_KEY, timeout=300)
def get_standing(start):
    profiles = UserProfile.sorted_by_ratings()[start: start + 10]
    attachments = []
    for k, profile in enumerate(profiles):
        user = profile.user
        attachments.append({
            'color': DIVISION_COLORS.get(get_color(profile.rating), '#000000'),
            'author_name': '%d - %s' % (start + k + 1, user.username),
            'author_icon': 'http://matcomgrader.com' + (
                profile.avatar.url if profile.avatar else '/static/mog/images/avatar.jpg'
            ),
            'fields': [
                {
                    'title': 'Rating',
                    'value': profile.rating,
                    'short': True
                },
                {
                    'title': 'Points',
                    'value': profile.points,
                    'short': True
                },
                {
                    'title': 'Contests',
                    'value': user.instances.count(),
                    'short': True
                },
                {
                    'title': 'Submissions',
                    'value': user.submissions.filter(hidden=False).count(),
                    'short': True
                },
            ]
        })
    return attachments
