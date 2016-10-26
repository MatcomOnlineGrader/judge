from .base import *

DEBUG = True

INSTALLED_APPS += [
    'debug_toolbar'
]

MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware'
]

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'mog',
        'USER': 'mog',
        'PASSWORD': 'mog',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Uncomment this to work with debug_toolbar
# INTERNAL_IPS = ['127.0.0.1']

# Place to store problem test-cases & pdf
PROBLEMS_FOLDER = '~/Desktop/problems/'

# The file backend writes emails to a file
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = os.path.join(BASE_DIR, '..', 'emails')
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025  # This value must match with the one in run_fake_smtp.sh
