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

## How to restore a database backup

In this part, I'll explain how to put a database snapshot into our development database. We'll assume you've already downloaded a backup file called `judge.sql` from the production system, and it's currently stored on your computer.

1. The initial step is to move the `judge.sql` file into the PostgreSQL Docker container. You can achieve this by using the command below:

```sh
docker cp ~/Downloads/judge.sql $(docker ps | grep postgres | cut -d' ' -f1):/
```

2. Next, you'll ssh in to the PostgreSQL Docker container using this command:

```sh
docker exec -it $(docker ps | grep postgres | cut -d' ' -f1) bash
```

3. Now, we have to remove the existing database before bringing back the old one. The challenge here is that we're currently using PostgreSQL 11, and there's no straightforward way to delete a database. Nevertheless, I found a solution on Stack Overflow that explains how to do it: [link to the answer](https://dba.stackexchange.com/a/11895).

Make sure no one can connect to your database:

```sh
psql -h localhost postgres judge -c \
    "UPDATE pg_database SET datallowconn = 'false' WHERE datname = 'judge';"
```

Force disconnection of all clients connected to this database, using:

```sh
psql -h localhost postgres judge -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'judge'";
```

And finally, delete the database:

```sh
psql -h localhost postgres judge -c \
    "DROP DATABASE judge;"
```

2. After we've deleted the judge database, we must create a "placeholder" where we can restore the database.

```sh
psql -h localhost postgres judge -c \
    "CREATE DATABASE judge OWNER judge;"
```

3. Finally, we need to restore the database from `judge.sql`:

```sh
psql -U judge < /judge.sql
```

🎥 You can see step by step in this video https://www.dropbox.com/scl/fi/beqyqobdrtxp98r52y5gm/restore-database-backup.mov?rlkey=6kelu7o98tqzyff8idk0inbru&dl=0
