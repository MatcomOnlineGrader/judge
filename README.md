Matcom Online Grader
===================

**MOG** is an online judge for the contestants of the ACM-ICPC of the Faculty of Mathematics and Computer Science of the University of Havana

[![](mog/static/mog/images/logo.png )](mog/static/mog/images/logo.png)

**Softwares**

- Postgres-9.5.*
- Python3
  - Install `pip`
  - Install `virtualenv`

**Secret file:**

Create a file named __settings.ini__ at the root of the project with the following content:

```
[debugging]
DEBUG: <bool> [true|false]
DEBUG_TOOLBAR: <bool> [true|false]

[database]
DATABASE_NAME: <str> [database name]
DATABASE_USER: <str> [database user]
DATABASE_PASS: <str> [database password]
DATABASE_HOST: <str> [localhost | xxx.xxx.xxx.xxx | mydomain.com]
DATABASE_PORT: <int> [5432 for PostgreSQL, 3306 for MySQL, etc]
REPLICAS: <int> [use 0 here as default]

[secrets]
SECRET_KEY: <str> [random string]
PASSWORD_GENERATOR_SECRET_KEY: <str> [constant string to generate default password, don't change it often]

[email]
EMAIL_USE_TLS: <bool> [true|false]
EMAIL_HOST: <str> [SMTP host]
EMAIL_PORT: <int> [SMTP port]
EMAIL_HOST_USER: <str> [email host user]
EMAIL_HOST_PASSWORD: <str> [email host password]
DEFAULT_FROM_EMAIL: <str> [default from email]
EMAIL_TIMEOUT: <int>

[others]
MEDIA_ROOT: <str> [path to media folder]
STATIC_ROOT: <str> [path to static folder]

[grader]
GRADER_ID: simple [choose which grader to use. runexe is only available in windows, simple should work on all platforms.]
RESOURCES_FOLDER: <str> [path to resources folder]
SANDBOX_FOLDER: <str> [path to sandbox folder]
PROBLEMS_FOLDER: <str> [path to problems folder]

[cache]
BACKEND: <str> [redis, memcached, in-memory, etc]
LOCATION: <str> [depends on the backend]

[palantir]
LOG_REQUESTS: <bool> [true if we want to store detailed request logs]
```

You can use the following script to generate the settings:

```bash
./generate_test_settings.sh
```

**Postgres:**

Execute `psql` and run:

```
postgres=# CREATE USER [DATABASE_USER] PASSWORD '[DATABASE_PASS]';
postgres=# CREATE DATABASE [DATABASE_NAME] OWNER [DATABASE_USER];
postgres=# GRANT postgres TO [DATABASE_USER];
postgres=# ALTER USER [DATABASE_USER] CREATEDB;
```

**Run some python scripts:**

Create and activate a virtual environment (optional):

- `virtualenv venv`
- `venv\Scripts\activate`     # Windows
- `source venv/bin/activate`  # Linux

Install pip requirements:

```
(venv) - pip install -r requirements.txt
```

Migrate tables into the database:

```
(venv) - python manage.py migrate
```

Create the compiled file used by django to manage translation:

```
(venv) - python manage.py compilemessages -l es
```

Copy static files to the folder specified by the `STATIC_ROOT` variable in django settings:

```
(venv) - python manage.py collectstatic
```

Generate some data to start developing (using) the platform:
**WARNING**: Only do this to run the platform in development mode locally.

```
export MOG_LOCAL_DEV=1
(venv) - python manage.py populate_local_dev -d
```

Launch the grader using:

```
(venv) - python manage.py runserver
```
