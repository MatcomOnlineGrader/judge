#!/bin/bash
if [ ! -f "settings.ini" ]; then
  perl -pe 's/secret_auto_fillable_placeholder/substr("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",rand()*62,12)/ge' settings.ini.template > settings.ini
fi

database_pass=$(awk -F ":" '/DATABASE_PASS/ {gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' settings.ini)

DOCKER_BUILDKIT=0 DATABASE_PASS=$database_pass \
    docker-compose -f docker/dev/docker-compose.yml up
