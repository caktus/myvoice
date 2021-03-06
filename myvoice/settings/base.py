import datetime
import os

from celery.schedules import crontab
import djcelery


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, os.pardir))

DEBUG = True
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('MyVoice Team', 'myvoice-team@caktusgroup.com'),
    ('Bayo Opadeyi', 'bayokrapht@gmail.com'),
)

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'myvoice',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Africa/Lagos'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale.
USE_L10N = True

# If you set this to False, Django will not use timezone-aware datetimes.
USE_TZ = True

# Absolute filesystem path to the directory that will hold user-uploaded files.
# Example: "/home/media/media.lawrence.com/media/"
MEDIA_ROOT = os.path.join(PROJECT_ROOT, 'public', 'media')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'public', 'static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Additional locations of static files
STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'static'),
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = '&)lv%ki)l90pcsfvdxl4j$&st*)g45)un%te3+xpfwul2!=dxs'

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.core.context_processors.tz',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'myvoice.clinics.context_processors.facilities',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'pagination.middleware.PaginationMiddleware',
)

ROOT_URLCONF = 'myvoice.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'myvoice.wsgi.application'

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'templates'),
)

FIXTURE_DIRS = (
    os.path.join(BASE_DIR, 'fixtures'),
)

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.sitemaps',
    'django.contrib.gis',

    # External apps
    "rapidsms",
    'south',
    'compressor',
    "django_nose",
    "widget_tweaks",
    "djcelery",
    # "djtables",  # required by rapidsms.contrib.locations
    "django_tables2",
    "selectable",
    'pagination',
    'sorter',
    'leaflet',

    # RapidSMS
    "rapidsms.backends.database",
    "rapidsms.contrib.handlers",
    "rapidsms.contrib.httptester",
    "rapidsms.contrib.messagelog",
    "rapidsms.contrib.messaging",
    "rapidsms.contrib.registration",
    "rapidsms.contrib.echo",

    # Internal apps
    "myvoice.core",
    "myvoice.clinics",
    "myvoice.statistics",
    "myvoice.survey",

    "rapidsms.contrib.default",  # Must be last
]

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'basic': {
            'format': '%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'basic',
            'filename': os.path.join(PROJECT_ROOT, 'myvoice.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 10,
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins', 'file'],
            'level': 'ERROR',
            'propagate': True,
        },
        'celery': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
        },
        'myvoice': {
            'handlers': ['mail_admins', 'file'],
            'level': 'DEBUG',
        },
    }
}

# Application settings
SKIP_SOUTH_TESTS = True

COMPRESS_PRECOMPILERS = (
    ('text/less', 'lessc {infile} {outfile}'),
)

SORTER_ALLOWED_CRITERIA = {
    'sort_rules': ['id', 'keyword', 'source', 'dest', 'message', 'rule_type',
                   'label'],
    'sort_broadcasts': ['id', 'date', 'schedule_frequency', 'body'],
    'sort_messages': ['broadcast__id', 'broadcast__body', 'date_created',
                      'status', 'recipient', 'date_sent'],
}

INSTALLED_BACKENDS = {
    "message_tester": {
        "ENGINE": "rapidsms.backends.database.DatabaseBackend",
    },
}

LOGIN_REDIRECT_URL = '/'

RAPIDSMS_HANDLERS = (
    'rapidsms.contrib.echo.handlers.echo.EchoHandler',
    'rapidsms.contrib.echo.handlers.ping.PingHandler',
)

djcelery.setup_loader()

CELERYBEAT_SCHEDULE = {
    'import-responses': {
        'task': 'myvoice.survey.tasks.import_responses',
        'schedule': crontab(minute='0', hour='*'),
    },
}
CELERY_SEND_TASK_ERROR_EMAILS = True
CELERY_ROUTES = {
    # process the time-sensitive tasks that send SMSes on their own queue
    'myvoice.survey.tasks.start_feedback_survey': {'queue': 'sendsms'},
    'myvoice.survey.tasks.handle_new_visits': {'queue': 'sendsms'},
    # put import_responses on its own queue so it doesn't back up other tasks
    # if it gets delayed
    'myvoice.survey.tasks.import_responses': {'queue': 'importer'},
}

# Set PostGIS version so that Django can find it.
# See http://stackoverflow.com/questions/10584852/my-postgis-database-looks-fine-but-geodjango-thinks-otherwise-why  # noqa
POSTGIS_VERSION = (2, 1)

TEXTIT_API_TOKEN = os.environ.get('TEXTIT_API_TOKEN', '')
TEXTIT_USERNAME = os.environ.get('TEXTIT_USERNAME', '')
TEXTIT_PASSWORD = os.environ.get('TEXTIT_PASSWORD', '')

# Amount of time that should elapse between when we first process a visit
# and when we send a survey to the patient.
DEFAULT_SURVEY_DELAY = datetime.timedelta(minutes=0)

# Hours, in UTC, between which we can send surveys. Send dates outside of this
# window will be sent the next day.
SURVEY_TIME_WINDOW = (7, 20)  # 7am (8am WAT) to 8pm (9pm WAT)
