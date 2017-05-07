#!/usr/bin/env bash
export DJANGO_SETTINGS_MODULE='judge.settings'
gunicorn judge.wsgi
