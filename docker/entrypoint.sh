#!/bin/sh
set -e

cd /app

# Run database migrations (Alembic reads DATABASE_URL from env)
echo "Running database migrations..."
alembic upgrade head

echo "Starting API server..."
exec "$@"
