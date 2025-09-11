"""
Django settings for cfa_backend proj# Security settings
SECURE_PROXY_SSL_HEADER = None
SECURE_SSL_REDIRECT = False

# CORS settings
CORS_ORIGIN_ALLOW_ALL = True  # For development only
CORS_ALLOW_CREDENTIALS = True  # Required for cookies
CORS_ALLOW_ALL_ORIGINS = True  # For development only

CORS_ALLOWED_ORIGINS = [
    "http://192.168.1.15:8000",
    "http://192.168.1.15:8081",
    "http://localhost:8081",
    "http://localhost:8000",
    "http://10.0.2.2:8000",
    "exp://t9zkygu-nileshsan-8081.exp.direct",
    "exp://192.168.0.104:8081"
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'api-key',
]ated by 'django-admin startproject' using Django 5.2.3.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

from pathlib import Path
import os
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-rzncfab_$tqb+00sssy9ilh@+0+(3lkjc(q-ciy$#^6qf55y43'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True  # Temporarily set to True to see detailed errors

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '168.231.121.11',
    '*',  # Temporarily allow all hosts
]

# Security settings
SECURE_PROXY_SSL_HEADER = None
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# CSRF Settings
CSRF_COOKIE_NAME = 'csrftoken'
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = None  # Allow cross-site requests
CSRF_COOKIE_AGE = 31449600  # 1 year in seconds
CSRF_USE_SESSIONS = False
CSRF_COOKIE_DOMAIN = None
CSRF_COOKIE_SECURE = False
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://0.0.0.0:8000",
    "http://localhost:8081",
    "http://10.0.2.2:8000",
    "http://192.168.1.15:8000",
    "http://192.168.1.15:8081",
    "exp://192.168.1.13:8081"
]

# Disable CSRF for development
CSRF_EXEMPT_ROUTES = [
    '/api/login/',
    '/api/transactions/',
    '/api/model/',
    '/api/payment-predictions/',
]

def csrf_exempt_middleware(get_response):
    def middleware(request):
        if any(request.path.startswith(route) for route in CSRF_EXEMPT_ROUTES):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return get_response(request)
    return middleware

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'cfa_backend.settings.csrf_exempt_middleware',  # Add our custom middleware
]

# API Authentication
API_KEY = '5ac22546aab77b566c262459e5cc19e8055f4418'

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),  # Increased to 12 hours
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),  # 30 days refresh token
    'ROTATE_REFRESH_TOKENS': True,  # Get new refresh token with every refresh
    'UPDATE_LAST_LOGIN': True,  # Track last login
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# CORS and CSRF settings
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CSRF_USE_SESSIONS = False
CSRF_COOKIE_HTTPONLY = False
CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOWED_ORIGINS = [
    "http://192.168.1.15:8000",
    "http://192.168.1.15:8081",
    "http://localhost:8081",
    "http://localhost:8000",
    "exp://t9zkygu-nileshsan-8081.exp.direct",
    "exp://192.168.0.104:8081"
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Disable CSRF for API endpoints
CSRF_TRUSTED_ORIGINS = [
    'http://192.168.0.104:8000',
    'http://192.168.0.104:8081',
    'exp://192.168.0.104:8081'
]

# CORS settings
CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# CSRF settings
CSRF_TRUSTED_ORIGINS = [
    'http://192.168.0.104:8000',
    'http://192.168.0.104:8081',
    'exp://192.168.0.104:8081'
]

# CSRF settings for development
CSRF_COOKIE_NAME = 'csrftoken'
CSRF_COOKIE_SECURE = False  # Set to True in production
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False
CSRF_COOKIE_DOMAIN = None

# API settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_bootstrap5',
    'widget_tweaks',
    'django_filters',
    'corsheaders',  # CORS support
    'rest_framework.authtoken',  # token authentication
    'rest_framework_simplejwt',
    'core',
    'transactions',
    'accounts',
]

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
}

# CORS settings
CORS_ALLOW_ALL_ORIGINS = True  # For development only
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.0.104:8000",
    "http://192.168.0.104:8081",
    "http://168.231.121.11:8000",
    "exp://192.168.0.104:8081",
]

# Additional CORS settings
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# CORS Allow Methods
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'accounts': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'transactions': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Must be at the top
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # Add CSRF middleware
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CSRF Configuration
CSRF_EXEMPT_URLS = [
    r'^/login/$',
    r'^/api/login/$',
    r'^/api/token/$',
    r'^/api/token/refresh/$',
]

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://192.168.0.104:8000',
    'http://168.231.121.11:8000',
]

# Updated CORS settings for mobile app
CORS_ALLOWED_ORIGINS = [
    # Local development
    "http://localhost:8000",
    "http://localhost:8081",
    "http://localhost:19000",
    
    # Local network
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8081",
    "http://127.0.0.1:19000",
    
    # Android emulator
    "http://10.0.2.2:8000",
    "http://10.0.2.2:8081",
    "http://10.0.2.2:19000",
    
    # Expo development
    "exp://192.168.0.104:8081",
    "http://192.168.0.104:8081",
    
    # Production (add your production URLs here)
    "http://168.231.121.11:8000",
]

ROOT_URLCONF = 'cfa_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cfa_backend.wsgi.application'
ASGI_APPLICATION = 'cfa_backend.asgi.application'

# Database
import os
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# Using Hostinger MySQL database for both development and production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'u782070381_CFA_project_DB',
        'USER': 'u782070381_PBS_Solutions',
        'PASSWORD': 'pbscfaAI25',
        'HOST': '217.21.91.74',
        'PORT': '3306',
        'OPTIONS': {
            'sql_mode': 'STRICT_TRANS_TABLES',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
            'connect_timeout': 60,
            'read_timeout': 60,
            'write_timeout': 60,
        },
        'CONN_MAX_AGE': 60,
        'ATOMIC_REQUESTS': True,
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

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# OAuth / Social client config (read from environment in development)
GOOGLE_OAUTH_CONFIG = {
    'web_client_id': os.environ.get('GOOGLE_WEB_CLIENT_ID'),
    'android_client_id': os.environ.get('GOOGLE_ANDROID_CLIENT_ID', '695786750606-a1054qioo3rjmggghgkg7gn52mq37rtv.apps.googleusercontent.com'),
    'ios_client_id': os.environ.get('GOOGLE_IOS_CLIENT_ID'),
    'web_client_secret': os.environ.get('GOOGLE_WEB_CLIENT_SECRET'),
    'authorized_redirect_uris': [
        'https://auth.expo.io/@nileshsan/cfa-mobile',
        'cfa-ai-app://',
        'com.googleusercontent.apps.695786750606-a1054qioo3rjmggghgkg7gn52mq37rtv:/oauth2redirect'
    ]
}

# For backward compatibility
SOCIAL_GOOGLE_CLIENT_ID = GOOGLE_OAUTH_CONFIG['web_client_id']
SOCIAL_GOOGLE_CLIENT_SECRET = GOOGLE_OAUTH_CONFIG['web_client_secret']

AUTHENTICATION_BACKENDS = [
    'accounts.backends.CustomUserBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# File upload settings
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'accounts.authentication.BearerTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'EXCEPTION_HANDLER': 'accounts.exceptions.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day'
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10
}

# Logging configuration to show INFO-level logs for custom loggers in the console
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'tally_transaction_import': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cfa.transactions': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cfa.token_auth': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}