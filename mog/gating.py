#-----------------------------------------------------------------------
# Legacy permissions based on user only
#-----------------------------------------------------------------------

def user_is_admin(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_admin


#-----------------------------------------------------------------------
# New permission model based on ContestPermission table
#-----------------------------------------------------------------------

def user_is_judge_in_contest(user, contest):
    """Does the user has role judge in contest?"""
    return __user_has_role_in_contest(user, contest, 'judge')


def user_is_observer_in_contest(user, contest):
    """Does the user has role observer in contest?"""
    return __user_has_role_in_contest(user, contest, 'observer')


def user_is_judge_in_submission_contest(user, submission):
    """Does user has judge role in the contest which submission belongs to?"""
    return user_is_judge_in_contest(user, submission.problem.contest)


def user_is_observer_in_submission_contest(user, submission):
    """Does user has judge observer in the contest which submission belongs to?"""
    return user_is_observer_in_contest(user, submission.problem.contest)


def user_can_bypass_frozen_in_contest(user, contest):
    """return True iff logged user can see submissions and standing in frozen/death time"""
    return user_is_admin(user) or user_is_observer_in_contest(user, contest) or user_is_judge_in_contest(user, contest)


def grant_role_to_user_in_contest(user, contest, role):
    __add_user_role_to_contest(user, contest, role, True)


def revoke_role_to_user_in_contest(user, contest, role):
    __add_user_role_to_contest(user, contest, role, False)


def get_all_contest_for_judge(user):
    return __get_all_contest_for_role(user, 'judge')


def get_all_contest_for_observer(user):
    return __get_all_contest_for_role(user, 'observer')

#-----------------------------------------------------------------------
# Bellow there are "private" functions only that shouldn't be used
# directly outside this file. Use those functions defined above that
# calls into the private ones.
#-----------------------------------------------------------------------

def __user_has_role_in_contest(user, contest, role):
    contest_id = contest if type(contest) is int else contest.pk
    return contest_id in __get_all_contest_for_role(user, role)


def __get_all_contest_for_role(user, role):
    """
    This function returns the list of contests that user was granted
    role of type `role`. The ContestPermission table stores permission
    roles incrementally where the latest row for (user, contest, role)
    contains the `granted` value that is the one that confers privileges
    to the contest.

    Parameters
    ----------
    user: User,
        User we are looking
    role: str,
        Currently, this is limited to "judge"|"observer" only but might
        be expanded in the future.

    Returns
    -------
    List[int],
        List of contest ids that `user` has the role of `role`.

    TODO(leandro): Add a cache here since the contest permission list
    shouldn't be modified too often.
    """
    # TODO(leandro): Remove circular dependency :(
    from api.models import ContestPermission
    if not user or not user.is_authenticated:
        return []
    permissions = ContestPermission.objects.\
        filter(user=user, role=role).order_by('-pk')
    contests = {}
    for permission in permissions:
        if permission.contest_id not in contests:
            contests[permission.contest_id] = permission.granted
    return [
        contest_id for contest_id,granted in contests.items() if granted
    ]


def __add_user_role_to_contest(user, contest, role, granted):
    # TODO(leandro): Remove circular dependency :(
    from api.models import ContestPermission
    ContestPermission.objects.create(
        user=user, contest=contest, role=role, granted=granted
    )
