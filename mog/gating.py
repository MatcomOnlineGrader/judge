def user_is_admin(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_admin


def user_is_browser(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_browser


def user_is_judge(user):
    """return True iff logged user is judge"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_judge


def user_is_observer_in_contest(user, contest):
    """return True iff logged user is observer"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_observer


def user_is_judge_in_contest(user, contest):
    """return True iff logged user is judge"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_judge


def user_can_bypass_frozen_in_contest(user, contest):
    """return True iff logged user can see submissions and standing in frozen/death time"""
    return user_is_admin(user) or user_is_observer_in_contest(user, contest) or user_is_judge_in_contest(user, contest)
