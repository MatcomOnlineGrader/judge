from django import template
from mog.utils import user_is_admin, user_is_browser

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
    return user_is_admin(user) or user_is_browser(user) or user == submission.user


@register.filter()
def can_see_details_of(user, submission):
    return submission.can_show_details_to(user)


@register.filter()
def can_see_judgment_details_of(user, submission):
    return submission.can_show_judgment_details_to(user)


@register.filter()
def can_send_message_to(user1, user2):
    return user1.is_authenticated() and user1 != user2


@register.filter()
def can_see_profile_of(user1, user2):
    return user1.is_authenticated() and (user_is_admin(user1) or user1 == user2)


@register.filter()
def can_edit_post(user, post):
    return user.is_authenticated() and (user_is_admin(user) or user == post.user)


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
    return user.is_authenticated() and (user.profile.is_admin or user == user2)


@register.filter()
def can_see_tags(user):
    if not user.is_authenticated() or not hasattr(user, 'profile'):
        return True
    return user.profile.show_tags


@register.filter()
def can_edit_comment(user, comment):
    return user_is_admin(user)
