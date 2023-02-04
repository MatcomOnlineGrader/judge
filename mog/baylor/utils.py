from django.conf import settings
from hashlib import sha256

ICPCID_GUEST_PREFIX = 'guestid_'

def generate_secret_password(user_id):
    """
    Generate password
    """
    return sha256( (settings.PASSWORD_GENERATOR_SECRET_KEY + str(user_id)).encode() ).hexdigest()[:10]


def hash_string(value):
    return sha256(value.encode()).hexdigest()[:20]
