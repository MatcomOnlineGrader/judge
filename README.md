Matcom Online Grader
===================

**MOG** is an online judge for the contestants of the ACM-ICPC of the Faculty of Mathematics and Computer Science of the University of Havana

[![](mog/static/mog/images/logo.png )](mog/static/mog/images/logo.png)

**Softwares**
- Postgres-9.5.*
- Python-2.7.*
    - Install `pip`
    - Install `virtualenv`

**requirements.txt**

- beautifulsoup4==4.5.1
- Django==1.10.1
- django-debug-toolbar==1.6
- django-registration==2.1.2
- Pillow==3.3.1
- psycopg2==2.6.2
- sqlparse==0.2.1

**Secret file:**

Create a file named __settings.ini__ at the root of the project with the following content:

```
[debugging]
DEBUG: true|false
DEBUG_TOOLBAR: true|false

[database]
DATABASE_NAME: database_name
DATABASE_USER: database_user
DATABASE_PASS: database_pass
DATABASE_HOST: localhost | xxx.xxx.xxx.xxx | mydomain.com
DATABASE_PORT: 5432

[secrets]
SECRET_KEY: secret_key

[email]
EMAIL_USE_TLS: true
EMAIL_HOST: smtp.gmail.com
EMAIL_PORT: 587
EMAIL_HOST_USER: email_host_user
EMAIL_HOST_PASSWORD: email_host_password
DEFAULT_FROM_EMAIL: default_from_email

[others]
PROBLEMS_FOLDER: problem_folder
MEDIA_ROOT: media_root
STATIC_ROOT: static_root
```

**Postgres:**

Execute `psql` and run:
```
postgres=# CREATE USER [DATABASE_USER] PASSWORD '[DATABASE_PASS]';
postgres=# CREATE DATABASE [DATABASE_NAME] OWNER [DATABASE_USER];
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
