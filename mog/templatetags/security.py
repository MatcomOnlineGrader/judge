from django import template
from mog.gating import user_is_admin, user_is_judge_in_contest

register = template.Library()


@register.filter()
def is_admin(user):
    return user_is_admin(user)


@register.filter()
def can_see_code_of(user, submission):
    """
    Return true iff @user can see source code of
    @submission. This can happens iff @user is
    CodeBrowser, Admin or the owner of @submission.
    """
    return submission.can_show_source_to(user)


@register.filter()
def can_see_details_of(user, submission):
    return submission.can_show_details_to(user)


@register.filter()
def can_rejudge(user, submission):
    return submission.can_be_rejudged_by(user)


@register.filter()
def can_see_judgment_details_of(user, submission):
    return submission.can_show_judgment_details_to(user)


@register.filter()
def can_send_message_to(user1, user2):
    return user1.is_authenticated and user1 != user2


@register.filter()
def can_see_profile_of(user1, user2):
    return user1.is_authenticated and (user_is_admin(user1) or user1 == user2)


@register.filter()
def can_edit_post(user, post):
    return user.is_authenticated and (user_is_admin(user) or user == post.user)


@register.filter()
def can_see_contest(user, contest):
    return contest.can_be_seen_by(user)


@register.filter()
def can_create_contest(user):
    return user_is_admin(user)


@register.filter()
def can_create_problem(user):
    return user_is_admin(user)


@register.filter()
def can_edit_contest(user, contest):
    return user_is_admin(user)


@register.filter()
def can_see_saris(user, contest):
    return contest.can_show_saris_to(user)


@register.filter()
def can_edit_problem(user, problem):
    return user_is_admin(user)


@register.filter()
def can_register_for_real(user, contest):
    return contest.can_register_for_real(user)


@register.filter()
def can_register_for_virtual(user, contest):
    return contest.can_register_for_virtual(user)


@register.filter()
def registered_for_real(user, contest):
    return contest.registered_for_real(user)


@register.filter()
def registered_for_virtual(user, contest):
    return contest.registered_for_virtual(user)


@register.filter()
def can_edit_profile(user, user2):
    return user.is_authenticated and (user.profile.is_admin or user == user2)


@register.filter()
def can_see_tags(user):
    if not user.is_authenticated or not hasattr(user, 'profile'):
        return True
    return user.profile.show_tags


@register.filter()
def can_edit_comment(user, comment):
    return comment.can_be_edited_by(user)


@register.filter()
def can_remove_comment(user, comment):
    return comment.can_be_removed_by(user)


@register.filter()
def can_edit_clarification(user, contest):
    return user_is_admin(user) or user_is_judge_in_contest(user, contest)


@register.filter()
def can_create_clarification(user, contest):
    """Determines whether an user can create a clarification
    or not in a contest. `user` can ask for clarification in
    `contest` if the following conditions met:

    - `user` is authenticated
    - `contest` is running
    - `user` is registered in `contest`

    If `user` is an admin, then he/she can create a clarification
    under any situation.

    Parameters
    ----------
    contest : Contest,
              A contest instance.

    user : User,
           An user instance.

    Returns
    -------
    bool
        True only if `user` can ask for clarification in `contest`.
        False otherwise.
    """
    if user_is_admin(user) or user_is_judge_in_contest(user, contest):
        return True
    return user.is_authenticated and (contest.is_running and contest.real_registration(user))


@register.filter()
def can_comment_on_post(user, post):
    return post.can_be_commented_by(user)
