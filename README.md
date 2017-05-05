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

Create a file named __secrets.json__ at the root of the project with the following content:

```
{
    "production": {
        "SECRET_KEY": "[PRODUCTION_SECRET_KEY]",
        "DATABASE_HOST": "[PRODUCTION_DATABASE_HOST]",
        "DATABASE_NAME": "[PRODUCTION_DATABASE_NAME]",
        "DATABASE_USER": "[PRODUCTION_DATABASE_USERNAME]",
        "DATABASE_PASS": "[PRODUCTION_DATABASE_PASSWORD]",
        "DATABASE_PORT": "[PRODUCTION_DATABASE_PORT]",
        "EMAIL_USER": "[PRODUCTION_EMAIL_USER]",
        "EMAIL_PASS": "[PRODUCTION_EMAIL_PASSWORD]",
        "PROBLEMS_FOLDER": "[PATH_TO_THE_PROBLEMS_FOLDER]"
    }
}
```

Usual values are:

- `PRODUCTION_SECRET_KEY`: Long random string.
- `PRODUCTION_DATABASE_HOST`: `localhost` if database and app in the same machine.
- `PRODUCTION_DATABASE_PORT`: 5432 (we are using PostgreSQL)
- `PATH_TO_THE_PROBLEMS_FOLDER`: Path to problems folder containing sample inputs/outputs and test cases.

**Postgres:**

Execute `psql` and run:
```
postgres=# CREATE USER [PRODUCTION_DATABASE_USERNAME] PASSWORD '[PRODUCTION_DATABASE_PASSWORD]';
postgres=# CREATE DATABASE [PRODUCTION_DATABASE_NAME] OWNER [PRODUCTION_DATABASE_USERNAME];
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
(venv) - python manage.py migrate --settings=judge.settings.production
```

Create the compiled file used by django to manage translation:
```
(venv) - python manage.py compilemessages -l es --settings=judge.settings.production
```

Copy static files to the folder specified by the `STATIC_ROOT` variable in django settings:
```
(venv) - python manage.py collectstatic --settings=judge.settings.production
```
