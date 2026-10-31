"""Production settings. Used by wsgi.py / asgi.py by default.

Required environment variables:
    DJANGO_SECRET_KEY      a long random secret
    DJANGO_ALLOWED_HOSTS   comma-separated host names, e.g. "eventease.com,www.eventease.com"
"""

from .base import *  # noqa: F401,F403

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

DEBUG = False

ALLOWED_HOSTS = [h.strip() for h in os.environ['DJANGO_ALLOWED_HOSTS'].split(',') if h.strip()]

# Collected static files (python manage.py collectstatic)
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Email over SMTP. Without DJANGO_EMAIL_HOST nothing can be sent, so mail is written to
# the server log instead of failing silently: a password reset that goes nowhere is worse
# than one you can find in the log.
EMAIL_HOST = os.environ.get('DJANGO_EMAIL_HOST', '')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = int(os.environ.get('DJANGO_EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = os.environ.get('DJANGO_EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_USE_SSL = os.environ.get('DJANGO_EMAIL_USE_SSL', 'False').lower() == 'true'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# HTTPS hardening
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
