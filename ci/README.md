# How to add another "App Server" from scratch in DigitalOcean

## What is an "App Server" ?

An "App Server" is simply a server running django alone without PostgreSQL. The connection to the database is done remotely since it could live in any other external machine. App servers receive connection forwarded from the Load-Balancer. All app servers are considered stateless for now and we can't can keep status in memory/cache assumming that subsequent requests will come to the same server.

## Glossary

All references to a droplet, app server or server will refer to the same, a "virtual server" living in DigitalOcean. A "DB Server" refers to a "virtual server" where a Postgres server is living potentially allowing connections from app servers.

## Prerequisites

This doc assume that we start from an empty Droplet in DigitalOcean (Ubuntu 18.04). To see how to create one, visit https://www.digitalocean.com/docs/droplets/how-to/create/.

It also assume that you have an account in GitLab with access to the "Matcom Online Grader" repo (judge).

## Initial Server Setup with Ubuntu 18.04
First, SSH into your server as root `ssh root@XXX.XXX.XXX.XXX` and execute the script https://raw.githubusercontent.com/do-community/automated-setups/master/Ubuntu-18.04/initial_server_setup.sh replacing `USERNAME=sammy` by `USERNAME=fito`. This setup assumes we will have two users: `root` and `fito` (with sudo permissions).

If you want to understand the script above, you can read the step-by-step explanation in https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu-18-04.

## Finish new user instalation
Change to user `fito` since we don't want to use `root` to host the app (too scary) and change `fito`'s password. Execute `cd ~` to change the current directory to `fito` home. The following steps:

```
root@server:~# sudo su fito
fito@server:/root$ cd ~
fito@server:~$ passwd
Changing password for fito.
(current) UNIX password:
...
```

Now, lets create a SSH key that will be helpful to access the remote git repo (judge). Just do `ssh-keygen`.

To avoid re-typing the passphrase (if any) everytime, lets ssh-add once and avoid the retyping:

```
$ eval `ssh-agent -s`
$ ssh-add
```

## Clone repo

Now, copy the ssh public key (output of the command bellow) to allow us to clone the repo.

```
fito@droplet-name:~$ cat ~/.ssh/id_rsa.pub
ssh-rsa ... fito@droplet-name
```

Now, add that key to your GitLab account, go to https://gitlab.com/profile/keys.

Clone judge repository in the home directory and once the repo is cloned, change the current directory to the project folder:

```
fito@droplet-name:~$ git clone git@gitlab.com:lcastillov/judge.git
fito@droplet-name:~$ cd judge
fito@droplet-name:~/judge$ 
```

## File setting
For security reasons the configuration file settings.ini is encrypted with production ready data. To decrypt it, run the following command:

```
fito@droplet-name:~/judge$ gpg --decrypt --pinentry-mode=loopback ci/settings.ini.asc > settings.ini
```

It will ask for the password, if you don't know it, then ask for it :)

## Database connection
Ensure the IP of the current droplet is whitelisted for every database server.

## Execute the script to configure django/gunicorn/nginx

The script is basically an extract of the article https://www.digitalocean.com/community/tutorials/how-to-set-up-django-with-postgres-nginx-and-gunicorn-on-ubuntu-18-04.

```
fito@droplet-name:~/judge$ ./ci/ci.sh
```

## Test
Now you can visit http://XXX.XXX.XXX.XXX where `XXX.XXX.XXX.XXX` is the IP assigned to the current server.

# Load Balancer
Write here how to include this new server in the load-balancer.
