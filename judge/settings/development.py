from .base import *

DEBUG = True

# Secret key
SECRET_KEY = get_secret_value('development', 'SECRET_KEY')


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': get_secret_value('development', 'DATABASE_HOST'),
        'PORT': get_secret_value('development', 'DATABASE_PORT'),
        'NAME': get_secret_value('development', 'DATABASE_NAME'),
        'USER': get_secret_value('development', 'DATABASE_USER'),
        'PASSWORD': get_secret_value('development', 'DATABASE_PASS'),
    }
}

# Debug Toolbar
# INSTALLED_APPS += [
#     'debug_toolbar'
# ]
#
# MIDDLEWARE += [
#     'debug_toolbar.middleware.DebugToolbarMiddleware'
# ]
#
# INTERNAL_IPS = ['127.0.0.1']

# Place to store problem test-cases ( secret location )
PROBLEMS_FOLDER = get_secret_value('development', 'PROBLEMS_FOLDER')

# The file backend writes emails to a file
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = os.path.join(BASE_DIR, '..', 'emails')
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025  # This value must match with the one in run_fake_smtp.sh
