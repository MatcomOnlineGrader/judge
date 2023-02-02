from django.conf import settings
from hashlib import sha256


def generate_secret_password(user_id):
    """
    Generate password
    """
    return sha256( (settings.PASSWORD_GENERATOR_SECRET_KEY + str(user_id)).encode() ).hexdigest()[:10]
