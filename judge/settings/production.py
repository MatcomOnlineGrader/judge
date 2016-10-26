from .base import *

DEBUG = False

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'mog',
        'USER': 'mog',
        'PASSWORD': 'fert21',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_USE_TLS = True
EMAIL_PORT = 25
EMAIL_HOST = 'mail.matcom.uh.cu'
EMAIL_HOST_USER = 'mog'
EMAIL_HOST_PASSWORD = 'mog_pepe'
DEFAULT_FROM_EMAIL = 'mog@matcom.uh.cu'

# Place to store problem test-cases & pdf
PROBLEMS_FOLDER = '/home/mog/problems/'
