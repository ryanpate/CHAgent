"""
Django settings for Cherry Hills Worship Arts Portal.
"""
import os
from pathlib import Path

# Try to import dj_database_url, fall back gracefully if not available
try:
    import dj_database_url
    HAS_DJ_DATABASE_URL = True
except ImportError:
    HAS_DJ_DATABASE_URL = False

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# Allowed hosts - Railway sets RAILWAY_PUBLIC_DOMAIN
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Add Railway domain if available
RAILWAY_PUBLIC_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if RAILWAY_PUBLIC_DOMAIN:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)

# Allow all .railway.app domains and custom domain in production
if not DEBUG:
    ALLOWED_HOSTS.extend(['.railway.app', '.up.railway.app', 'aria.church', '.aria.church'])

# CSRF trusted origins for Railway and custom domains
CSRF_TRUSTED_ORIGINS = [
    'https://*.railway.app',
    'https://*.up.railway.app',
    'https://aria.church',
    'https://*.aria.church',
]
if RAILWAY_PUBLIC_DOMAIN:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RAILWAY_PUBLIC_DOMAIN}')
CSRF_TRUSTED_ORIGINS.extend([
    origin.strip() for origin in
    os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django_htmx',
    'accounts',
    'core',
    'blog',
    'axes',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'core.middleware.TenantMiddleware',  # Multi-tenant organization middleware
    'core.middleware.TwoFactorMiddleware',  # 2FA enforcement
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
                'core.context_processors.organization_context',  # Multi-tenant context
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Also check for Railway's PostgreSQL-specific variable
if not DATABASE_URL:
    DATABASE_URL = os.environ.get('DATABASE_PUBLIC_URL', '')

# Default to SQLite for local development only
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Use PostgreSQL if DATABASE_URL is set
if DATABASE_URL and HAS_DJ_DATABASE_URL:
    # Handle Railway's postgres:// vs postgresql:// URL schemes
    db_url = DATABASE_URL
    if db_url.startswith('postgres://'):
        # dj_database_url handles both formats, but let's be explicit
        pass

    try:
        DATABASES['default'] = dj_database_url.config(
            default=db_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
        # Log success (will show in Railway logs)
        print(f"[DATABASE] Using PostgreSQL database")
    except Exception as e:
        print(f"[DATABASE] ERROR: Failed to configure PostgreSQL: {e}")
        print(f"[DATABASE] WARNING: Falling back to SQLite - DATA WILL NOT PERSIST!")
elif DATABASE_URL and not HAS_DJ_DATABASE_URL:
    print("[DATABASE] ERROR: DATABASE_URL is set but dj-database-url is not installed!")
    print("[DATABASE] WARNING: Falling back to SQLite - DATA WILL NOT PERSIST!")
elif not DATABASE_URL:
    # Only acceptable for local development
    if not DEBUG:
        print("[DATABASE] WARNING: No DATABASE_URL set in production!")
        print("[DATABASE] WARNING: Using SQLite - DATA WILL NOT PERSIST ACROSS DEPLOYS!")
    else:
        print("[DATABASE] Using SQLite for local development")

# Password validation
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
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Denver'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Only include static dir if it exists
_static_dir = BASE_DIR / 'static'
if _static_dir.exists():
    STATICFILES_DIRS = [_static_dir]
else:
    STATICFILES_DIRS = []

# WhiteNoise configuration - use simpler storage that doesn't require manifest
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication URLs
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'

# AI API Keys
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# SongBPM API for BPM lookups (https://getsongbpm.com)
SONGBPM_API_KEY = os.environ.get('SONGBPM_API_KEY', '')

# Optional: Planning Center Integration
PLANNING_CENTER_APP_ID = os.environ.get('PLANNING_CENTER_APP_ID', '')
PLANNING_CENTER_SECRET = os.environ.get('PLANNING_CENTER_SECRET', '')

# Web Push Notifications (VAPID keys)
# Generate VAPID keys with: npx web-push generate-vapid-keys
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_CLAIMS_EMAIL = os.environ.get('VAPID_CLAIMS_EMAIL', 'mailto:support@aria.church')

# Security settings (for production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    # HSTS - enforce HTTPS for 1 year
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Referrer policy
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Session timeout (applies in all environments)
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

# =============================================================================
# Stripe Billing Configuration (for SaaS subscriptions)
# =============================================================================
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

# Stripe Price IDs (set these after creating products in Stripe Dashboard)
STRIPE_PRICE_IDS = {
    'starter_monthly': os.environ.get('STRIPE_PRICE_STARTER_MONTHLY', ''),
    'starter_yearly': os.environ.get('STRIPE_PRICE_STARTER_YEARLY', ''),
    'team_monthly': os.environ.get('STRIPE_PRICE_TEAM_MONTHLY', ''),
    'team_yearly': os.environ.get('STRIPE_PRICE_TEAM_YEARLY', ''),
    'ministry_monthly': os.environ.get('STRIPE_PRICE_MINISTRY_MONTHLY', ''),
    'ministry_yearly': os.environ.get('STRIPE_PRICE_MINISTRY_YEARLY', ''),
}

# =============================================================================
# Multi-Tenant SaaS Configuration
# =============================================================================
# Trial period length in days
TRIAL_PERIOD_DAYS = int(os.environ.get('TRIAL_PERIOD_DAYS', '14'))

# Default AI assistant name for new organizations
DEFAULT_AI_ASSISTANT_NAME = os.environ.get('DEFAULT_AI_ASSISTANT_NAME', 'Aria')

# App domain for subdomain routing (e.g., "aria.church" or "localhost:8000")
APP_DOMAIN = os.environ.get('APP_DOMAIN', 'localhost:8000')

# Whether to use subdomain-based tenant routing
USE_SUBDOMAIN_ROUTING = os.environ.get('USE_SUBDOMAIN_ROUTING', 'false').lower() == 'true'

# =============================================================================
# Email Configuration
# =============================================================================
# Use console backend for development, SMTP for production
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.resend.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = 'resend'
    EMAIL_HOST_PASSWORD = os.environ.get('RESEND_API_KEY', '')

DEFAULT_FROM_EMAIL = 'Aria <notifications@aria.church>'
EMAIL_REPLY_TO = 'support@aria.church'

# Site URL for building absolute URLs in emails
SITE_URL = os.environ.get('SITE_URL', 'https://aria.church')

# =============================================================================
# Login Rate Limiting (django-axes)
# =============================================================================
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.5  # 30 minutes (in hours)
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
