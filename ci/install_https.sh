#!/bin/sh
sudo systemctl stop nginx

sudo rm -r /etc/letsencrypt

sudo mkdir /etc/letsencrypt

sudo cp -r ./ci/letsencrypt/* /etc/letsencrypt/

sudo cp ./ci/judge.nginx.https.conf /etc/nginx/sites-available/judge

sudo rm /etc/nginx/sites-enabled/judge

sudo ln -s /etc/nginx/sites-available/judge /etc/nginx/sites-enabled

sudo systemctl start nginx
