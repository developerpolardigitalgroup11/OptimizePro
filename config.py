import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Default database configuration
_default_db = 'sqlite:///' + os.path.join(BASE_DIR, 'optimize_pro.db')
_database_url = os.environ.get('DATABASE_URL', _default_db)

# Heroku/Render uses 'postgres://' but SQLAlchemy needs 'postgresql://'
if _database_url.startswith('postgres://'):
    _database_url = _database_url.replace('postgres://', 'postgresql://', 1)

_is_postgres = _database_url.startswith('postgresql')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'optimize-pro-dev-secret-key-change-in-prod')
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        **({'pool_size': 10, 'max_overflow': 20} if _is_postgres else {}),
    }
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max upload
    IS_POSTGRES = _is_postgres

    # ML Configuration
    FORECAST_HORIZON = 14  # days
    MIN_DATA_SMA = 7
    MIN_DATA_EXP_SMOOTH = 14
    MIN_DATA_HOLT_WINTERS = 30
    SAFETY_FACTOR = 1.5
    DEFAULT_LEAD_TIME = 7  # days

    # Cache TTL (seconds)
    CACHE_TTL_ANALYTICS = 300  # 5 minutes
    CACHE_TTL_FORECASTS = 86400  # 24 hours
    CACHE_TTL_ALERTS = 60  # 1 minute

    # Alert Thresholds
    CRITICAL_DAYS = 3
    HIGH_ALERT_DAYS = 7
    OVERSTOCK_MULTIPLIER = 2  # 2x forecast horizon = overstock

    # Allocation
    MIN_ALLOCATION_PER_MARKETPLACE = 5

    # Currency
    CURRENCY_SYMBOL = '₹'
