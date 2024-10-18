FROM python:3.7

# Update/Upgrade apt before doing anything else
RUN apt-get update
RUN apt-get upgrade -y

# Copy project content in the host machine into the container
# as /code folder.
RUN mkdir /code
WORKDIR /code
COPY . /code/

# Install all python dependencies.
RUN pip install -r requirements.txt

# Create some folders that will be used by the web server.
RUN mkdir -p /var/www/judge/static
RUN mkdir -p /var/www/judge/media

# Install safeexec
RUN apt-get install cmake make git g++
RUN bash ci/make_safeexec.sh && safeexec --exec /bin/true

# Move all static files (js, images, css, etc.) into
# `/var/www/judge/static` folder. This folder path
# must match with `STATIC_ROOT` in the `settings.ini`
# config file.
RUN python manage.py collectstatic --noinput
