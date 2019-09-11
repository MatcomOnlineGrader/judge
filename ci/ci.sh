# Some reading on how this was setup:
# https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu-18-04
#
# NOTE: This script doesn't install PostgreSQL. We assume that postgres
# database is living somewhere else and not inside this server.

IP=$(ifconfig eth0 | grep -m1 inet | tr -s ' ' | cut -d' ' -f3)

# Creating the PostgreSQL Database and User
sudo apt update
sudo apt install python3-pip \
    python3-dev \
    libpq-dev \
    nginx \
    curl \
    gettext <<< yes

# Add fito to www-data group
sudo usermod -a -G www-data fito

# Creating a Python Virtual Environment for your Project
sudo -H pip3 install --upgrade pip
sudo -H pip3 install virtualenv

# Install dependencies
cd ~/judge
virtualenv venv
source venv/bin/activate
pip install -r app.server.requirements.txt

# Creating systemd Socket and Service Files for Gunicorn
sudo cp ./ci/gunicorn.socket /etc/systemd/system/
sudo cp ./ci/gunicorn.service /etc/systemd/system/

sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket

# Checking for the Gunicorn Socket File
sudo systemctl status gunicorn.socket
file /run/gunicorn.sock

# Configure Nginx to Proxy Pass to Gunicorn
sudo cp ./ci/judge.nginx.conf /etc/nginx/sites-available/judge

sudo sed -i "s/SERVER-IP-PLACEHOLDER/$IP/g" /etc/nginx/sites-available/judge

sudo ln -s /etc/nginx/sites-available/judge /etc/nginx/sites-enabled

sudo rm /etc/nginx/sites-enabled/default # remove default config

sudo nginx -t # test Nginx configuration for syntax errors by typing

sudo systemctl restart nginx

sudo ufw allow 'Nginx Full'

# Prepare static & media folders
sudo mkdir /var/www/judge
sudo mkdir /var/www/judge/media
sudo mkdir /var/www/judge/static

PYTHON=$(which python)
sudo $PYTHON manage.py collectstatic --noinput

sudo chmod -R 774 /var/www/judge/media
sudo chown -R www-data /var/www/judge/media
sudo chgrp -R www-data /var/www/judge/media

sudo chmod -R 544 /var/www/judge/static
sudo chown -R www-data /var/www/judge/static
sudo chgrp -R www-data /var/www/judge/static

# Generate translation file(s)
python manage.py compilemessages
