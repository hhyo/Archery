# -*- coding: UTF-8 -*-


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
from typing import List
from datetime import timedelta
import environ

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

environ.Env.read_env(os.path.join(BASE_DIR, '.env'))
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(List[str], ["*"]),
    SECRET_KEY=(str, 'hfusaf2m4ot#7)fkw#di2bu6(cv0@opwmafx5n#6=3d%x^hpl6'),
    DATABASE_URL=(str, "mysql://root:@127.0.0.1:3306/archery"),
    CACHE_URL=(str, "redis://127.0.0.1:6379/0"),
    DINGDING_CACHE_URL=(str, "redis://127.0.0.1:6379/1"),
    ENABLE_LDAP=(bool, False),
    AUTH_LDAP_ALWAYS_UPDATE_USER=(bool, True),
    AUTH_LDAP_USER_ATTR_MAP=(dict, {
        "username": "cn",
        "display": "displayname",
        "email": "mail"
    }),
    Q_CLUISTER_SYNC=(bool, False),  # qcluster 同步模式, debug 时可以调整为 True
    # CSRF_TRUSTED_ORIGINS=subdomain.example.com,subdomain.example2.com subdomain.example.com
    CSRF_TRUSTED_ORIGINS=(list, [])
)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# https://docs.djangoproject.com/en/4.0/ref/settings/#csrf-trusted-origins
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# 解决nginx部署跳转404
USE_X_FORWARDED_HOST = True

# 请求限制
DATA_UPLOAD_MAX_MEMORY_SIZE = 15728640

# Application definition
INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_q',
    'sql',
    'sql_api',
    'common',
    'rest_framework',
    'django_filters',
    'drf_spectacular',
)

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'common.middleware.check_login_middleware.CheckLoginMiddleware',
    'common.middleware.exception_logging_middleware.ExceptionLoggingMiddleware',
)

ROOT_URLCONF = 'archery.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'common/templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'common.utils.global_info.global_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'archery.wsgi.application'

# Internationalization
LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = False

# 时间格式化
USE_L10N = False
DATETIME_FORMAT = 'Y-m-d H:i:s'
DATE_FORMAT = 'Y-m-d'

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'common/static'), ]
STATICFILES_STORAGE = 'common.storage.ForgivingManifestStaticFilesStorage'

# 扩展django admin里users字段用到，指定了sql/models.py里的class users
AUTH_USER_MODEL = "sql.Users"

# 密码校验
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 9,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

############### 以下部分需要用户根据自己环境自行修改 ###################

# SESSION 设置
SESSION_COOKIE_AGE = 60 * 300  # 300分钟
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # 关闭浏览器，则COOKIE失效

# 该项目本身的mysql数据库地址
DATABASES = {
    'default': {
        **env.db(),
        **{
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'charset': 'utf8mb4'
            },
            'TEST': {
                'NAME': 'test_archery',
                'CHARSET': 'utf8mb4',
            }
        }
    }
}

# Django-Q
Q_CLUSTER = {
    'name': 'archery',
    'workers': 4,
    'recycle': 500,
    'timeout': 60,
    'compress': True,
    'cpu_affinity': 1,
    'save_limit': 0,
    'queue_limit': 50,
    'label': 'Django Q',
    'django_redis': 'default',
    'sync': env("Q_CLUISTER_SYNC")  # 本地调试可以修改为True，使用同步模式
}

# 缓存配置
CACHES = {
    "default": env.cache(),
    "dingding": env.cache_url("DINGDING_CACHE_URL")
}

# https://docs.djangoproject.com/en/3.2/ref/settings/#std-setting-DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# API Framework
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    # 鉴权
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    # 权限
    'DEFAULT_PERMISSION_CLASSES': ('sql_api.permissions.IsInUserWhitelist',),
    # 限速（anon：未认证用户  user：认证用户）
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '120/min',
        'user': '600/min'
    },
    # 过滤
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    # 分页
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 5,
}

# Swagger UI
SPECTACULAR_SETTINGS = {
    'TITLE': 'Archery API',
    'DESCRIPTION': 'OpenAPI 3.0',
    'VERSION': '1.0.0',
}

# API Authentication
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=4),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=3),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# LDAP
ENABLE_LDAP = env("ENABLE_LDAP", False)
if ENABLE_LDAP:
    import ldap
    from django_auth_ldap.config import LDAPSearch

    AUTHENTICATION_BACKENDS = (
        'django_auth_ldap.backend.LDAPBackend',  # 配置为先使用LDAP认证，如通过认证则不再使用后面的认证方式
        'django.contrib.auth.backends.ModelBackend',  # django系统中手动创建的用户也可使用，优先级靠后。注意这2行的顺序
    )

    AUTH_LDAP_SERVER_URI = env("AUTH_LDAP_SERVER_URI", default="ldap://xxx")
    AUTH_LDAP_USER_DN_TEMPLATE = env("AUTH_LDAP_USER_DN_TEMPLATE", default=None)
    if not AUTH_LDAP_USER_DN_TEMPLATE:
        del AUTH_LDAP_USER_DN_TEMPLATE
        AUTH_LDAP_BIND_DN = env("AUTH_LDAP_BIND_DN", default="cn=xxx,ou=xxx,dc=xxx,dc=xxx")
        AUTH_LDAP_BIND_PASSWORD = env("AUTH_LDAP_BIND_PASSWORD", default="***********")
        AUTH_LDAP_USER_SEARCH_BASE = env("AUTH_LDAP_USER_SEARCH_BASE", default="ou=xxx,dc=xxx,dc=xxx")
        AUTH_LDAP_USER_SEARCH_FILTER = env("AUTH_LDAP_USER_SEARCH_FILTER", default='(cn=%(user)s)')
        AUTH_LDAP_USER_SEARCH = LDAPSearch(AUTH_LDAP_USER_SEARCH_BASE, ldap.SCOPE_SUBTREE, AUTH_LDAP_USER_SEARCH_FILTER)
    AUTH_LDAP_ALWAYS_UPDATE_USER = env("AUTH_LDAP_ALWAYS_UPDATE_USER", default=True)  # 每次登录从ldap同步用户信息
    AUTH_LDAP_USER_ATTR_MAP = env("AUTH_LDAP_USER_ATTR_MAP")

# LOG配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[%(asctime)s][%(threadName)s:%(thread)d][task_id:%(name)s][%(filename)s:%(lineno)d][%(levelname)s]- %(message)s'
        },
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/archery.log',
            'maxBytes': 1024 * 1024 * 100,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'django-q': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/qcluster.log',
            'maxBytes': 1024 * 1024 * 100,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'default': {  # default日志
            'handlers': ['console', 'default'],
            'level': 'WARNING'
        },
        'django-q': {  # django_q模块相关日志
            'handlers': ['console', 'django-q'],
            'level': 'WARNING',
            'propagate': False
        },
        'django_auth_ldap': {  # django_auth_ldap模块相关日志
            'handlers': ['console', 'default'],
            'level': 'WARNING',
            'propagate': False
        },
        # 'django.db': {  # 打印SQL语句，方便开发
        #     'handlers': ['console', 'default'],
        #     'level': 'DEBUG',
        #     'propagate': False
        # },
        # 'django.request': {  # 打印请求错误堆栈信息，方便开发
        #     'handlers': ['console', 'default'],
        #     'level': 'DEBUG',
        #     'propagate': False
        # },
    }
}

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
if not os.path.exists(MEDIA_ROOT):
    os.mkdir(MEDIA_ROOT)

PKEY_ROOT = os.path.join(MEDIA_ROOT, 'keys')
if not os.path.exists(PKEY_ROOT):
    os.mkdir(PKEY_ROOT)

try:
    from local_settings import *
except ImportError:
    print("import local settings failed, ignored")
