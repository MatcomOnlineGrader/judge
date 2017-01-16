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
EMAIL_PORT = 25
EMAIL_HOST = 'mail.matcom.uh.cu'
EMAIL_HOST_USER = get_secret_value('production', 'EMAIL_USER'),
EMAIL_HOST_PASSWORD = get_secret_value('production', 'EMAIL_PASS'),
DEFAULT_FROM_EMAIL = 'mog@matcom.uh.cu'

# Place to store problem test-cases ( secret location )
PROBLEMS_FOLDER = get_secret_value('production', 'PROBLEMS_FOLDER')

# Statics
STATIC_ROOT = os.path.join(BASE_DIR, '../static')
