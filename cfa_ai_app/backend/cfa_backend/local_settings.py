from .settings import *

# Local development overrides
BASE_DIR = Path(__file__).resolve().parent.parent

# Use a local sqlite database for easy local development and to avoid remote MySQL connectivity
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    }
}

# Allow all hosts for local testing
ALLOWED_HOSTS = ['*']

# Debug on for local development
DEBUG = True
