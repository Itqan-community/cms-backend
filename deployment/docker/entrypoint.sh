#!/usr/bin/env bash
set -e

echo "Starting Django application..."

# Wait for database if DB_HOST is specified
if [ -n "${DB_HOST}" ]; then
    echo "Waiting for database at ${DB_HOST}:${DB_PORT:-5432}..."
    until nc -z "${DB_HOST}" "${DB_PORT:-5432}"; do
        echo "Database not ready, waiting..."
        sleep 1
    done
    echo "Database is ready!"
fi

# Run Django management commands
echo "Running database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create superuser if it doesn't exist
if [ -n "${DJANGO_SUPERUSER_EMAIL}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    echo "Creating superuser if not exists..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='${DJANGO_SUPERUSER_EMAIL}').exists():
    User.objects.create_superuser('${DJANGO_SUPERUSER_USERNAME:-admin}', '${DJANGO_SUPERUSER_EMAIL}', '${DJANGO_SUPERUSER_PASSWORD}')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
" || echo "Failed to create superuser"
fi

echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 config.wsgi
