#!/usr/bin/env bash
export DJANGO_SETTINGS_MODULE='judge.settings.development'
python -m smtpd -n -c DebuggingServer localhost:1025
