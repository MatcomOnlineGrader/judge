import html
import os

from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.safestring import mark_safe


def get_special_day(date):
    """
    Given a date returns a string describing
    whether that day is special or not. Non
    special days are considered regulars.
    - Valentine Day (February, 14)
    - Halloween (October, 31)
    - Thanksgiving (Fourth Thursday of November)
    - Christmas (19 to 31 of December)
    """
    day = 'regular'
    if date.month == 2 and date.day == 14:
        day = 'valentine'
    if date.month == 10 and date.day == 31:
        day = 'halloween'
    if date.month == 11 and 22 <= date.day <= 28 and date.weekday() == 3:
        day = 'thanksgiving'
    if date.month == 12 and 19 <= date.day <= 31:
        day = 'christmas'
    return day


def unescape(value):
    return mark_safe(html.unescape(value))


def secure_html(html):
    """
    Remove all scrips, forms & events on every tag in
    a chunk of HTML code
    """
    if not html:
        return html
    soup = BeautifulSoup(html, 'html5lib')
    # Remove all scripts
    for tag in soup.find_all('script'):
        tag.extract()
    # Remove all forms
    for tag in soup.find_all('form'):
        tag.extract()
    # Remove all attributes starting with on-
    # to avoid js execution when events fired.
    for tag in soup.findAll():
        for attr in tag.attrs.keys():
            if attr and attr.startswith('on'):
                del tag[attr]
    return soup.prettify()


def user_is_browser(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_browser


def user_is_admin(user):
    """return True iff logged user is administrator"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_admin


def user_is_observer(user):
    """return True iff logged user is observer"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_observer

def user_is_judge(user):
    """return True iff logged user is judge"""
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.is_judge


def user_can_bypass_frozen(user):
    """return True iff logged user can see submissions and standing in frozen/death time"""
    return user_is_admin(user) or user_is_browser(user) or user_is_observer(user) or user_is_judge(user)


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


def fix_problem_folder(problem):
    folders = [
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id)),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'inputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'outputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'sample inputs'),
        os.path.join(settings.PROBLEMS_FOLDER, str(problem.id), 'sample outputs'),
    ]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
