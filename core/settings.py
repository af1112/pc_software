"""
Django settings for core project.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Environment detection
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'local')

# Load environment-specific settings
if ENVIRONMENT == 'production':
    from .settings_production import *
elif ENVIRONMENT == 'local':
    try:
        from .settings_local import *
    except ImportError:
        # Fallback settings if settings_local doesn't exist
        SECRET_KEY = 'django-insecure-24^fn&q)8!c3q!jv*pf&mu!r5k9a2+_%b25*pmdao_og6v0#pv'
        DEBUG = True
        ALLOWED_HOSTS = ['*']
        CSRF_TRUSTED_ORIGINS = [
            'http://localhost:8000',
            'http://127.0.0.1:8000',
            'http://localhost:8010',
            'http://127.0.0.1:8010',
        ]
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
        MEDIA_URL = '/media/'
        MEDIA_ROOT = BASE_DIR / 'media'
        STATIC_URL = '/static/'
        STATIC_ROOT = BASE_DIR / 'staticfiles'
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
        SECURE_SSL_REDIRECT = False
        SECURE_HSTS_SECONDS = 0
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False
else:
    # Default fallback to local settings
    try:
        from .settings_local import *
    except ImportError:
        # Fallback settings if settings_local doesn't exist
        SECRET_KEY = 'django-insecure-24^fn&q)8!c3q!jv*pf&mu!r5k9a2+_%b25*pmdao_og6v0#pv'
        DEBUG = True
        ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
        CSRF_TRUSTED_ORIGINS = [
            'http://localhost:8000',
            'http://127.0.0.1:8000',
            'http://localhost:8010',
            'http://127.0.0.1:8010',
        ]
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
        MEDIA_URL = '/media/'
        MEDIA_ROOT = BASE_DIR / 'media'
        STATIC_URL = '/static/'
        STATIC_ROOT = BASE_DIR / 'staticfiles'
        EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
        SECURE_SSL_REDIRECT = False
        SECURE_HSTS_SECONDS = 0
        SESSION_COOKIE_SECURE = False
        CSRF_COOKIE_SECURE = False

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'apps.projects',
    'apps.reports',
    'apps.ai_engine',
    'apps.dms',
    'apps.users',
    'apps.expenses',
    'apps.ticketing',
    'apps.hr_attendance',
    'apps.organizations',
    'apps.hr_personnel',
    'apps.hrms',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.users.middleware.TenantMiddleware',
    'apps.users.middleware.UserLanguageMiddleware',
    'apps.users.middleware.LoginRequiredMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.users.context_processors.user_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database configuration is loaded from environment-specific settings files
# (settings_local.py for local development, settings_production.py for production)
# Do not add DATABASES configuration here as it will override environment settings.

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('fa', 'Persian'),
    ('ar', 'Arabic'),
    ('ur', 'Urdu'),
    ('hi', 'Hindi'),
    ('tr', 'Turkish'),
]

LOCALE_PATHS = [BASE_DIR / 'locale']

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

#WHITENOISE_USE_FINDERS = True
#WHITENOISE_MANIFEST_STRICT = False

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'main_dashboard'
LOGOUT_REDIRECT_URL = 'login'
