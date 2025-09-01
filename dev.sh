#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

trap 'echo; echo "Shutting down..."; kill $(jobs -p) 2>/dev/null || true' INT TERM EXIT

PYTHON_CMD="python3"
if ! command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python"
fi

PM="npm"
if [ -f "frontend/pnpm-lock.yaml" ]; then
  PM="pnpm"
elif [ -f "frontend/yarn.lock" ]; then
  PM="yarn"
elif [ -f "frontend/bun.lockb" ]; then
  PM="bun"
fi

export NEXT_PUBLIC_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://127.0.0.1:8000}"

# Uncomment the following lines to use PostgreSQL with Docker
# echo "Starting Docker services (PostgreSQL, Redis)..."
# docker-compose up -d
# echo "Waiting for PostgreSQL to be ready..."
# until docker-compose exec -T postgres pg_isready -U itqan_user -d itqan_cms; do
#   echo "Waiting for PostgreSQL..."
#   sleep 2
# done

echo "Starting backend (Django) on :8000..."
(
  cd backend
  source venv/bin/activate
  exec "$PYTHON_CMD" manage.py runserver 127.0.0.1:8000
) &

echo "Starting frontend (Next.js) on :3000..."
(
  cd frontend
  if [ "$PM" = "yarn" ]; then
    exec yarn dev
  else
    exec "$PM" run dev
  fi
) &

wait


