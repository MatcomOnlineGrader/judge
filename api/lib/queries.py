"""
This file contains a set of common queries that can be cached across
different sessions and shouldn't depend on the viewer status (guest,
authenticated, admin, etc).

Each "public" function that return the result of a query in this file
should describe the following sections:

- Description  : Description of the function, the function name along
                 with the argument should be self-explanatory. But we
                 might want to add more details.
- Uses cases   : Where this query will be used.
- Invalidation : When should we invalidate the cached result? The
                 invalidation part is very important to avoid having
                 outdated results. But having outdated results shouldn't
                 be serious issue for the query.
"""

from django.core.cache import cache

from api.lib import constants
from api.models import Post, UserProfile, ContestPermission, Contest
from mog.standing import calculate_standing_new


def cache_result(key, timeout=3600):
    def outer(func):
        def inner(*args, **kwargs):
            custom_key = key + "-".join([str(x).replace(" ", "_") for x in args])
            val = cache.get(custom_key)
            if val is None:
                val = func(*args, **kwargs)
                cache.set(custom_key, val, timeout)
            return val

        return inner

    return outer


@cache_result(key=constants.CACHE_KEY_FIVE_TOP_RATED_PROFILES)
def five_top_rated_profiles():
    """
    Description
    -----------
    Get the top five users with the highest ratings. If the ratings are
    equal for two users, then the one with more score will be ranked
    first. See, the sorted_by_ratings method in the UserProfile model.

    Uses cases
    ----------
    Used in the left panel in MOG under the "TOP RATED USERS" section.

    Invalidation
    ------------
    This query depends on two factors: rating and points. Rating is
    calculated adding up ratings from the RatingChange table. Points
    changes whenever a problem is solved.

    The tricky part is that the amount of points is calculated in the
    database using a Stored Procedure. So we don't have a clear way to
    detect that change.

    Our best effort as invalidation strategy is:
    - Invalidate when a contest is modified/removed, this is because
    once RatingChange are created/removed, the rated field of the
    corresponding contest changes. This way, we can detect that
    RatingChange objects were created/deleted.

    - Invalidate when a submission is modified/removed to detect points
    changes.
    """
    users = UserProfile.sorted_by_ratings().select_related("user")[:5]
    return list(users)


@cache_result(key=constants.CACHE_KEY_TEN_MOST_RECENT_POSTS)
def ten_most_recent_posts():
    """
    Description
    -----------
    This function get the ten most recent posts. The recency of a post
    is determined by the modification_date field that is updated
    whenever the post is updated or a comment is made.

    Uses cases
    ----------
    This will be used in the left panel in MOG under the "RECENT POSTS"
    section.

    Invalidation
    ------------
    Since the modification_date field is updated whenever the save
    method for a Post is called, we can invalidate the cache on Post
    modification.
    """
    posts = (
        Post.objects.order_by("-modification_date")
        .select_related("user")
        .select_related("user__profile")[:10]
    )
    return list(posts)


@cache_result(
    key=constants.CACHE_KEY_USER_CONTESTS, timeout=constants.USER_CONTESTS_TIMEOUT
)
def get_all_contest_for_role(user_id, role):
    """
    This function returns the list of contests that user was granted
    role of type `role`. The ContestPermission table stores permission
    roles incrementally where the latest row for (user, contest, role)
    contains the `granted` value that is the one that confers privileges
    to the contest.

    Parameters
    ----------
    user_id: User,
        User we are looking
    role: str,
        Currently, this is limited to "judge"|"observer" only but might
        be expanded in the future.

    Returns
    -------
    List[int],
        List of contest ids that `user` has the role of `role`.
    shouldn't be modified too often.
    """

    permissions = ContestPermission.objects.filter(user_id=user_id, role=role).order_by(
        "-pk"
    )
    contests = {}
    for permission in permissions:
        if permission.contest_id not in contests:
            contests[permission.contest_id] = permission.granted
    return list([contest_id for contest_id, granted in contests.items() if granted]) + [
        -1
    ]


def calculate_standing(
    contest, virtual=False, viewer_instance=None, group=None, bypass_frozen=False
):
    if virtual or bypass_frozen:
        return calculate_standing_new(
            contest, virtual, viewer_instance, group, bypass_frozen
        )
    else:
        return get_normal_standing(contest.id, group)


@cache_result(key=constants.CACHE_KEY_STANDING, timeout=constants.STANDING_TIMEOUT)
def get_normal_standing(contest_id, group):
    contest = Contest.objects.get(pk=contest_id)
    return calculate_standing_new(contest, False, None, group, False)
