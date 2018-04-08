Matcom Online Grader
===================

**MOG** is an online judge for the contestants of the ACM-ICPC of the Faculty of Mathematics and Computer Science of the University of Havana

[![](mog/static/mog/images/logo.png )](mog/static/mog/images/logo.png)

**Softwares**
- Postgres-9.5.*
- Python3
    - Install `pip`
    - Install `virtualenv`

**requirements.txt**

    beautifulsoup4==4.5.1
    colorama==0.3.9
    confusable-homoglyphs==2.0.2
    Django==2.0
    django-debug-toolbar==1.9.1
    django-registration==2.3
    html5lib==0.999999999
    Pillow==5.0.0
    psycopg2==2.6.2
    pytz==2017.3
    six==1.10.0
    sqlparse==0.2.4
    webencodings==0.5.1

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

[secrets]
SECRET_KEY: <str> [random string]

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
RESOURCES_FOLDER: <str> [path to resources folder]
SANDBOX_FOLDER: <str> [path to sandbox folder]
PROBLEMS_FOLDER: <str> [path to problems folder]

[cache]
BACKEND: <str> [redis, memcached, in-memory, etc]
LOCATION: <str> [depends on the backend]
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
```
- virtualenv venv
- venv\Scripts\activate     # Windows
- source venv/bin/activate  # Linux
```


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
