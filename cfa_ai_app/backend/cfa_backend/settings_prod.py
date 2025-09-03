import os
from pathlib import Path
from .settings import *  # Import base settings

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'your-secret-key-here')

# Add your domain and server IP to allowed hosts
ALLOWED_HOSTS = [
    'cfa.pbssolutions.in',  # Add your domain
    '217.21.91.74',        # Add your server IP
    'localhost',
]

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'u782070381_CFA_project'),
        'USER': os.environ.get('DB_USER', 'u782070381_PBS_solutions'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'pbscfaAI25'),
        'HOST': os.environ.get('DB_HOST', '217.21.91.74'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}

# Static files configuration
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_URL = '/static/'

# Media files configuration
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CORS settings (if needed)
CORS_ALLOWED_ORIGINS = [
    "https://cfa.pbssolutions.in",
    # Add other allowed origins here
]

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
