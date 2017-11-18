#!/bin/sh

settings=""

settings=${settings}"[debugging]\n"
settings=${settings}"DEBUG: false\n"
settings=${settings}"DEBUG_TOOLBAR: false\n"

settings=${settings}"[database]\n"
settings=${settings}"DATABASE_NAME: default\n"
settings=${settings}"DATABASE_USER: postgres\n"
settings=${settings}"DATABASE_PASS: postgres\n"
settings=${settings}"DATABASE_HOST: postgres\n"
settings=${settings}"DATABASE_PORT: 5432\n"

settings=${settings}"[secrets]\n"
settings=${settings}"SECRET_KEY: dhs7bvc2r*li%9jjf6^e25#y9du-rcj_5+=t9arf308p4)zpu!\n"

settings=${settings}"[email]\n"
settings=${settings}"EMAIL_USE_TLS: true\n"
settings=${settings}"EMAIL_HOST: -\n"
settings=${settings}"EMAIL_PORT: 587\n"
settings=${settings}"EMAIL_HOST_USER: -\n"
settings=${settings}"EMAIL_HOST_PASSWORD: -\n"
settings=${settings}"DEFAULT_FROM_EMAIL: -\n"

settings=${settings}"[others]\n"
settings=${settings}"STATIC_ROOT: -\n"
settings=${settings}"MEDIA_ROOT: -\n"

settings=${settings}"[grader]\n"
settings=${settings}"RESOURCES_FOLDER: -\n"
settings=${settings}"SANDBOX_FOLDER: -\n"
settings=${settings}"PROBLEMS_FOLDER: -"

if [ ! -f "settings.ini" ]
then
    echo -e ${settings} > "settings.ini"
fi
