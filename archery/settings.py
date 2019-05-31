# -*- coding: UTF-8 -*- 


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'hfusaf2m4ot#7)fkw#di2bu6(cv0@opwmafx5n#6=3d%x^hpl6'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

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
    'themis',
    'common',
)

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
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
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'archery',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': '127.0.0.1',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4'
        },
        'TEST': {
            'NAME': 'test_archery',
            'CHARSET': 'utf8mb4',
        },
    }
}

# themis审核所需mongodb数据库，账号角色必须有"anyAction" to "anyResource"权限
MONGODB_DATABASES = {
    "default": {
        "NAME": 'themis',
        "USER": '',
        "PASSWORD": '',
        "HOST": '127.0.0.1',
        "PORT": 27017,
    },
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
    'sync': False  # 本地调试可以修改为True，使用同步模式
}

# 缓存配置
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# LDAP
ENABLE_LDAP = False
if ENABLE_LDAP:
    import ldap
    from django_auth_ldap.config import LDAPSearch

    AUTHENTICATION_BACKENDS = (
        'django_auth_ldap.backend.LDAPBackend',  # 配置为先使用LDAP认证，如通过认证则不再使用后面的认证方式
        'django.contrib.auth.backends.ModelBackend',  # django系统中手动创建的用户也可使用，优先级靠后。注意这2行的顺序
    )

    AUTH_LDAP_SERVER_URI = "ldap://xxx"
    AUTH_LDAP_USER_DN_TEMPLATE = "cn=%(user)s,ou=xxx,dc=xxx,dc=xxx"
    AUTH_LDAP_ALWAYS_UPDATE_USER = True  # 每次登录从ldap同步用户信息
    AUTH_LDAP_USER_ATTR_MAP = {  # key为archery.sql_users字段名，value为ldap中字段名，用户同步信息
        "username": "cn",
        "display": "displayname",
        "email": "mail"
    }

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
            'filename': 'downloads/log/archery.log',
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
            'level': 'DEBUG'
        },
        'django-q': {  # django_q模块相关日志
            'handlers': ['console', 'default'],
            'level': 'DEBUG',
            'propagate': False
        },
        'django_auth_ldap': {  # django_auth_ldap模块相关日志
            'handlers': ['console', 'default'],
            'level': 'DEBUG',
            'propagate': False
        },
        # 'django.db': {  # 打印SQL语句，方便开发
        #     'handlers': ['console', 'default'],
        #     'level': 'DEBUG',
        #     'propagate': False
        # },
        'django.request': {  # 打印请求错误堆栈信息，方便开发
            'handlers': ['console', 'default'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
}
