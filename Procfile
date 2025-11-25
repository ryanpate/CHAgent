web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --preload --access-logfile - --error-logfile -
release: python manage.py collectstatic --noinput && python manage.py migrate && python manage.py create_superuser_from_env
