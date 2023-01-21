import html
import os

from bs4 import BeautifulSoup
from django.conf import settings
from django.utils.safestring import mark_safe
from api.lib import constants
from hashlib import sha256


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


def user_rating(user):
    """return user rating"""
    return user.profile.rating if hasattr(user, 'profile') else 0


def generate_secret_password(user_id):
    """
    Generate password
    """
<<<<<<< HEAD
    return sha256( (settings.PASSWORD_GENERATOR_SECRET_KEY + str(user_id)).encode() ).hexdigest()[:10]
=======
    return sha256( (constants.DJANGO_SECRET + str(user_id)).encode() ).hexdigest()[:10]
>>>>>>> ba781aa3 (generate password)
