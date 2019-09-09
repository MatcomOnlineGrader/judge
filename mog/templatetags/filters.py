from django.core.cache import cache
from django.utils.safestring import mark_safe
from django import template
from django import forms

from api.models import Division, Result
import api.utils as api_utils
import humanize

register = template.Library()


def get_color(rating):
    """Given a rating value returns the color of the corresponding division"""
    value = max(rating or 0, 0)
    divisions = cache.get('divisions')
    if divisions is None:
        divisions = Division.objects.order_by('-rating').all()
        cache.set('divisions', divisions)
    for division in divisions:
        if value >= division.rating:
            return division.color
    return 'black'


@register.filter()
def put_into_array(obj):
    """Used to put a single submission into an array and reuse
     submission lists template.
    """
    return [obj]


@register.filter()
def rating(user):
    result = cache.get(user.id)
    if result is None:
        result = user.profile.rating if hasattr(user, 'profile') else 0
        cache.set(user.id, result, 5 * 60)  # 5 minutes
    return result


@register.filter()
def user_color(user):
    return get_color(rating(user))


@register.filter()
def rating_color(rating):
    return get_color(rating or 0)


@register.filter(needs_autoscape=True)
def colorize_rating(rating):
    html = '<strong style="color:{0};">{1}</strong>'.format(
        get_color(rating), rating
    )
    return mark_safe(html)


@register.filter()
def percent(num, den):
    return 0 if den == 0 else num * 100 // den


@register.filter()
def user_stats(user):
    data = {
        'rating': 0, 'points': 0, 'solved': 0,
        'accepted': 0, 'submissions': 0,
    }
    if hasattr(user, 'profile'):
        profile = user.profile
        data['rating'] = profile.rating
        data['points'] = profile.points
        data['solved'] = profile.solved_problems
        data['accepted'] = profile.accepted_submissions
        data['submissions'] = profile.total_submissions
    return data


@register.filter()
def avatar(user):
    return api_utils.get_avatar_url_for_user(user)


modes = {
    'c': ('clike', 'text/x-csrc'),
    'c++': ('clike', 'text/x-c++src'),
    'cpp': ('clike', 'text/x-c++src'),
    'csharp': ('clike', 'text/x-csharp'),
    'java': ('clike', 'text/x-java'),
    'javascript': ('javascript', 'text/javascript'),
    'pascal': ('pascal', 'text/x-pascal'),
    'python': ('python', 'text/x-python'),
    'python2': ('python', 'text/x-python'),
    'python3': ('python', 'text/x-python'),
    'haskell': ('haskell', 'text/x-haskell'),
    'fsharp': ('mllike', 'text/x-fsharp'),
    'sql': ('sql', 'text/x-sql'),
    'asm': ('gas', 'text/x-gas'),
}


@register.filter()
def compiler_mime(compiler):
    if compiler is None or not hasattr(compiler, 'name'):
        return 'default'
    return modes.get(compiler.language.lower(), ('default', 'default'))[1]


@register.filter()
def compiler_mode(compiler):
    if compiler is None or not hasattr(compiler, 'name'):
        return None
    return modes.get(compiler.language.lower(), ('default', 'default'))[0]


@register.filter()
def theme_name(user):
    if hasattr(user, 'profile'):
        return user.profile.theme
    return 'default'


@register.filter()
def theme_url(user):
    if hasattr(user, 'profile'):
        return 'mog/plugins/codemirror/theme/%s.css' % user.profile.theme
    return None


@register.filter()
def user_problem_status(problem, user):
    # TODO: Maybe pass this query to the model with the
    # purpose of add cache ?
    if user.is_authenticated:
        submissions = problem.submissions.filter(user=user)
        if submissions.filter(result__name__iexact='accepted').count() > 0:
            return 'accepted'
        if submissions.count() > 0:
            return 'attempted'


@register.filter()
def inteq(a, b):
    if a is None or b is None:
        return False
    a, b = str(a), str(b)
    if not a.isdigit() or not b.isdigit():
        return False
    return a == b


@register.filter()
def is_checkbox(field):
    return type(field.field) is forms.fields.BooleanField


@register.filter()
def to(lo, hi):
    return range(lo, hi + 1)


@register.filter()
def add_class(element, _class):
    if isinstance(element.field, forms.fields.FileField):
        return element.as_widget()
    return element.as_widget(attrs={'class': _class, 'placeholder': element.label})


@register.filter()
def unseen_comments(user, post):
    return post.unseen_comments(user)


@register.filter()
def unseen_clarifications(user, contest):
    return contest.unseen_clarifications(user)


def unpack_seconds(seconds):
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = ((seconds % 86400) % 3600) // 60
    s = ((seconds % 86400) % 3600) % 60
    return d, h, m, s


def unpack_delta(delta):
    return unpack_seconds(int(delta.total_seconds()))


@register.filter()
def format_seconds(delta):
    d, h, m, s = unpack_delta(delta)
    if d > 0:
        return '%d:%02d:%02d:%02d' % (d, h, m, s)
    return '%02d:%02d:%02d' % (h, m, s)


@register.filter()
def format_minutes(delta):
    d, h, m, _ = unpack_delta(delta)
    if d > 0:
        return '%d:%02d:%02d' % (d, h, m)
    return '%02d:%02d' % (h, m)


@register.filter()
def format_penalty(penalty):
    d, h, m, s = unpack_seconds(int(penalty * 60))
    if d > 0:
        return '%d:%02d:%02d:%02d' % (d, h, m, s)
    return '%02d:%02d:%02d' % (h, m, s)


@register.filter()
def result_by_name(name):
    results = cache.get('results')
    if results is None:
        results = {}
        for result in Result.objects.all():
            results[result.name.lower()] = result.id
        cache.set('results', results)
    return results.get(name)


@register.filter()
def format_memory(memory):
    return humanize.naturalsize(memory)


@register.filter()
def first_problem(contest):
    return contest.problems.order_by('position').first()


@register.filter()
def get_instance(user, contest):
    return contest.registration(user)


@register.filter()
def has_solved_problem(instance, problem):
    return instance and instance.has_solved_problem(problem)


@register.filter()
def has_failed_problem(instance, problem):
    return instance and instance.has_failed_problem(problem)


# Remove following filters
@register.filter()
def explore(obj):
    return str(dir(obj))


@register.filter()
def type_(obj):
    return str(type(obj))


@register.filter()
def explore_dict(obj):
    return '\n'.join(str((k, v)) for k, v in obj.items())
