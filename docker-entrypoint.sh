#!/bin/sh
# docker-entrypoint.sh — Cloud Notes container startup script.
#
# 1. Waits up to 60 seconds for the database to be ready by retrying
#    `flask init-db` (which performs a real DB connection).
# 2. Launches gunicorn with the Cloud Notes app factory.

set -e

echo "==> Waiting for database to be ready..."
MAX_ATTEMPTS=30        # 30 x 2 s = 60 s maximum wait
ATTEMPT=0

until flask init-db 2>&1; do
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
    echo "ERROR: Database did not become ready within 60 seconds. Aborting."
    exit 1
  fi
  echo "    Database not ready yet (attempt $ATTEMPT/$MAX_ATTEMPTS). Retrying in 2 s..."
  sleep 2
done

echo "==> Database is ready. Starting gunicorn..."
exec gunicorn "app:create_app()" \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --threads 4 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
