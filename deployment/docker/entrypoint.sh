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

# NOTE: migrate, collectstatic and compilemessages are intentionally NOT run here.
#
# They are slow, and we don't want a new container to be considered "ready" until
# they're done. So the deploy pipeline runs all three as blocking one-off steps
# (`docker compose run --rm web ...`) BEFORE the web/celery containers are
# recreated. The old container keeps serving while they run; the new container
# then starts with only gunicorn, so it boots fast and is ready almost immediately.
#
# For standalone/manual runs of this image, set RUN_PREP=1 to run them here.
if [ "${RUN_PREP:-0}" = "1" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput

    echo "Collecting static files..."
    python manage.py collectstatic --noinput

    echo "Compiling translations..."
    python manage.py compilemessages --locale ar
fi

echo "Starting Gunicorn (ASGI, Uvicorn workers)..."
exec gunicorn config.asgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-10}" \
    --worker-class config.workers.DjangoUvicornWorker \
    --timeout 600
