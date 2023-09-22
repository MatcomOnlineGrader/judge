from api.models import Contest
from mog.gating import (
    get_all_contest_for_judge,
    user_is_admin,
    user_is_judge_in_contest,
)


def can_create_problem_in_contest(user, contest):
    """
    Used to show the create problem link in the problems view for a
    contest. This function is also used to ensure the actor in the create
    problem request has permission to create such problem in the given
    contest.

    Global admins can always create a problem. Users will be allowed to
    create a problem only in those contests they are judges of.
    """
    return user_is_admin(user) or user_is_judge_in_contest(user, contest)


def get_all_contests_a_user_can_create_problems_in(user):
    if user_is_admin(user):
        return Contest.objects.all().values_list("id", flat=True)
    return get_all_contest_for_judge(user)
