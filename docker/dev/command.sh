#!/bin/sh

# Run the webpack server in watch/development mode.
npm start &

# Run all migrations at the start. The developer can run
# this command at any point during development, but this
# ensures the initial setup is ready.
/opt/environ/bin/python3 manage.py migrate

# Let's run the webserver in a loop so the developer doesn't
# need to recreate the container if something breaks. This is
# useful when modifying packages in `requirements.txt`` while
# uninstalling Django or other core packages that might cause
# the server to crash.
while true; do
    /opt/environ/bin/python3 manage.py runserver 0.0.0.0:8000
    echo "Server crashed or stopped. Restarting in 5 seconds..."
    sleep 5
done
