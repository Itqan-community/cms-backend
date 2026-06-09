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

# Run migrations + collectstatic only when explicitly requested.
#
# In production these are run as a single one-off step by the deploy pipeline
# (BEFORE the web/celery containers are recreated) so that:
#   - migrations run exactly once, not once per container, and
#   - they don't race when web + celery + beat all boot together during a
#     rolling deploy.
# Set RUN_MIGRATIONS=1 to run them here instead (e.g. local/standalone runs).
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

echo "Compiling translations..."
python manage.py compilemessages --locale ar

echo "Starting Gunicorn server..."
exec gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 600 config.wsgi
