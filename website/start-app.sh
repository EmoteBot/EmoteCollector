#!/usr/bin/env sh
gunicorn --workers 1 --threads 4 --max-requests 10000 --reload --bind 0.0.0.0:8080 app_wsgi
