import os

from django.conf import settings

from HTMLParser import HTMLParser
from django.utils.safestring import mark_safe


def unescape(value):
    return mark_safe(HTMLParser().unescape(value))


def user_is_browser(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated() and hasattr(user, 'profile') and user.profile.is_browser


def user_is_admin(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated() and hasattr(user, 'profile') and user.profile.is_admin


def user_rating(user):
    """return user rating"""
    return user.profile.rating if hasattr(user, 'profile') else 0


def get_tests(problem, folder):
    """get file names living in a problem folder"""
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder)
        if not os.path.exists(path) or not os.path.isdir(path):
            return []
        return sorted(os.listdir(path))
    return []


def handle_tests(problem, files, folder):
    """copy files into an specified problem folder"""
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder)
        if not os.path.exists(path) or not os.path.isdir(path):
            return
        for incoming_file in files:
            name = incoming_file.name.replace(' ', '_')  # grader issues
            with open(os.path.join(path, name), 'wb+') as f:
                for chunk in incoming_file.chunks():
                    f.write(chunk)
            incoming_file.close()


def handle_remove_test(problem, folder, test):
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        try:
            os.remove(path)
            return True
        except OSError:
            pass
    return False


def test_content(problem, folder, test):
    if folder in ['inputs', 'outputs', 'sample inputs', 'sample outputs']:
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        if os.path.exists(path):
            with open(path, 'r') as f:
                content = ''.join(f.readlines())
            return content
    return None


def write_to_test(problem, folder, test, content):
    if handle_remove_test(problem, folder, test):
        path = os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), folder, test)
        with open(path, 'w') as f:
            f.write(content)
