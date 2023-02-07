from django.conf import settings
from hashlib import sha256

ICPCID_GUEST_PREFIX = 'guestid_'

CSV_GUEST_HEADER = 'team_name,institution,coach,participant1,participant2,participant3,group'

def generate_secret_password(user_id):
    """
    Generate password
    """
    return sha256( (settings.PASSWORD_GENERATOR_SECRET_KEY + str(user_id)).encode() ).hexdigest()[:10]


def hash_string(value):
    return sha256(value.encode()).hexdigest()[:20]


def generate_username(prefix: str, id: int):
    return '%s%03d' % (prefix, id)