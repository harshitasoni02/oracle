#!/bin/bash
set -e

echo "Creating migrations..."
python manage.py makemigrations --noinput

echo "Running migrations..."
python manage.py migrate --noinput

echo "Setup complete."
exec "$@"
