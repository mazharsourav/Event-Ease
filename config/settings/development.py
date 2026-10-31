"""Local development settings. Used by manage.py by default."""

import time

from .base import *  # noqa: F401,F403

# SECURITY WARNING: development-only key; production reads DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-63+)pff_xlzt3#$wk!&hu0o9+)sp&k=&nt%atu!kf)=4ai(*k7',
)

DEBUG = True

# A new value on every server start, so CSS and JS edits show up without clearing the browser cache.
ASSET_VERSION = str(int(time.time()))

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']

# Mail is printed to the terminal running runserver. A password reset link is in that
# output, so the whole flow can be followed locally without an SMTP server.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
