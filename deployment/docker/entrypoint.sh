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

# Ensure superuser exists with correct password
if [ -n "${DJANGO_SUPERUSER_EMAIL}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
    echo "Ensuring superuser exists with correct password..."
    python manage.py ensure_superuser --reset-password || echo "Failed to create/update superuser"
fi

echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 120 config.wsgi
