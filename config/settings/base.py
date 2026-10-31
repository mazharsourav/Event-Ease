"""
Settings shared by every environment.

Environment-specific values (SECRET_KEY, DEBUG, ALLOWED_HOSTS) live in
development.py and production.py, which import everything from here.

https://docs.djangoproject.com/en/5.2/topics/settings/
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

import os
from pathlib import Path

# Project root (the folder containing manage.py).
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

LOCAL_APPS = [
    'apps.core',
    'apps.users',
    'apps.events',
    'apps.venues',
    'apps.reviews',
    'apps.payments',
    'apps.notifications',
    'apps.blog',
]

INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# All project templates live in templates/, grouped by app (templates/<app>/).
# APP_DIRS stays on so Django's own apps (e.g. admin) find their templates.
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.site_frame',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

# EventEase serves a Bangladeshi audience. Times are stored in UTC (USE_TZ) and
# shown in local time, so an 8 pm concert reads as 8 pm.
TIME_ZONE = 'Asia/Dhaka'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Appended to every static file URL by {% asset %}; bump it on each release so browsers reload CSS and JS.
ASSET_VERSION = '1'

# Media files (user uploads)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Login/Logout URLs
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'


# Email
# Development prints messages to the console (see development.py); production sends
# them over SMTP. The address below is what a password reset appears to come from.
DEFAULT_FROM_EMAIL = os.environ.get('DJANGO_DEFAULT_FROM_EMAIL', 'EventEase <no-reply@eventease.example.com>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# How long a password reset link stays usable. Django's default is three days, which is
# longer than a reset link needs to live.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24  # one day

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# SSLCommerz payment gateway
# Defaults are the public SSLCommerz sandbox test-store credentials.
SSLCOMMERZ_STORE_ID = os.environ.get('SSLCOMMERZ_STORE_ID', 'testbox')
SSLCOMMERZ_STORE_PASSWORD = os.environ.get('SSLCOMMERZ_STORE_PASSWORD', 'qwerty')
SSLCOMMERZ_IS_SANDBOX = os.environ.get('SSLCOMMERZ_IS_SANDBOX', 'True').lower() == 'true'

if SSLCOMMERZ_IS_SANDBOX:
    SSLCOMMERZ_INIT_URL = 'https://sandbox.sslcommerz.com/gwprocess/v4/api.php'
    SSLCOMMERZ_VALIDATION_URL = 'https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php'
else:
    SSLCOMMERZ_INIT_URL = 'https://securepay.sslcommerz.com/gwprocess/v4/api.php'
    SSLCOMMERZ_VALIDATION_URL = 'https://securepay.sslcommerz.com/validator/api/validationserverAPI.php'

PAYMENT_GATEWAY_CONFIG = {
    'bkash': {
        'enabled': True,
        'gateway': 'sslcommerz',
        'display_name': 'bKash',
        'icon': '📱',
        'color': '#e2136e'
    },
    'nagad': {
        'enabled': True,
        'gateway': 'sslcommerz',
        'display_name': 'Nagad',
        'icon': '💰',
        'color': '#f47920'
    },
    'credit_card': {
        'enabled': True,
        'gateway': 'sslcommerz',
        'display_name': 'Credit Card',
        'icon': '💳',
        'color': '#3498db'
    }
}
