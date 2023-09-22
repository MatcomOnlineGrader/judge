def get_avatar_url_for_user(user):
    if not hasattr(user, "profile") or not user.profile.avatar:
        return "/static/mog/images/avatar.jpg"
    return user.profile.avatar.url
