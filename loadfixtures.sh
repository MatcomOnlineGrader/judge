#!/bin/sh
# remove previous migrations
rm ./api/migrations/0*
python manage.py flush
# load migrations
python manage.py makemigrations api
python manage.py migrate
# load fixtures
python manage.py loaddata users.json
python manage.py loaddata institutions.json
python manage.py loaddata teams.json
python manage.py loaddata contests.json
python manage.py loaddata problems.json
python manage.py loaddata contest_instances.json
python manage.py loaddata posts.json
python manage.py loaddata compilers.json
python manage.py loaddata results.json
python manage.py loaddata profiles.json
python manage.py loaddata rating_changes.json
python manage.py loaddata divisions.json
python manage.py loaddata submissions.json
python manage.py loaddata tags.json
python manage.py loaddata comments.json
# create superuser
python manage.py createsuperuser --username=admin --email=mog-admin@matcom.uh.cu
