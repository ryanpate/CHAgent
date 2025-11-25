# Note: Railway uses startCommand from railway.toml which includes migrations
# This Procfile is kept for compatibility with other platforms (Heroku, etc.)
web: python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --preload --access-logfile - --error-logfile -
