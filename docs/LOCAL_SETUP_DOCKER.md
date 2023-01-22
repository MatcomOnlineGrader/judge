# Local set up using Docker

Start the containers executing:

```bash
docker compose up
```

With the containers running, get a shell into the container executing:

```bash
docker exec -it [CONTAINER_ID] bash
```

And following execute for database migrations.

```bash
python manage.py migrate
```

Following execute for create super user.

```bash
python manage.py createsuperuser
```

Restart the containers executing:

```bash
docker compose up -d
```
