from .base import *

DEBUG = False

# Secret key
SECRET_KEY = get_secret_value('production', 'SECRET_KEY')

ALLOWED_HOSTS = ['*']

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': get_secret_value('production', 'DATABASE_HOST'),
        'PORT': get_secret_value('production', 'DATABASE_PORT'),
        'NAME': get_secret_value('production', 'DATABASE_NAME'),
        'USER': get_secret_value('production', 'DATABASE_USER'),
        'PASSWORD': get_secret_value('production', 'DATABASE_PASS'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_HOST_USER = get_secret_value('production', 'EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = get_secret_value('production', 'EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = get_secret_value('production', 'DEFAULT_FROM_EMAIL')

# Place to store problem test-cases ( secret location )
PROBLEMS_FOLDER = get_secret_value('production', 'PROBLEMS_FOLDER')

# Media & Statics
STATIC_ROOT = '/var/www/judge/static/'
MEDIA_ROOT = '/var/www/judge/media/'
