#!/usr/bin/env bash
export DJANGO_SETTINGS_MODULE='judge.settings.production'
gunicorn judge.wsgi
