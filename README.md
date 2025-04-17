# Matcom Online Grader

[![](mog/static/mog/images/logo.png)](mog/static/mog/images/logo.png)

## Local set up using Docker

```bash
./updev.sh
```

## How to restore a database backup

Here, I'll show you how to load a database snapshot into your development database. We'll assume you've already downloaded a backup file called `judge.sql` from production and have it on your computer. Follow the steps in this video: [restore-database-backup.mov](https://www.dropbox.com/scl/fi/beqyqobdrtxp98r52y5gm/restore-database-backup.mov?rlkey=6kelu7o98tqzyff8idk0inbru&dl=0).


```sh
# Retrieve the Docker container ID from the Docker image.
CONTAINER_ID=$(docker ps -q --filter "ancestor=postgres:11.5")

# The first step is to move the `judge.sql` file into the
# PostgreSQL Docker container. Use the command below:
docker cp ~/Downloads/judge.sql $CONTAINER_ID:/

# Now, we need to remove the existing database before restoring the backup.
# The challenge is that we're using PostgreSQL 11, which doesn't have a simple
# way to delete a database. However, I found a solution on Stack Overflow:
# https://dba.stackexchange.com/a/11895.

# Make sure no one is connected to your database
docker exec -it $CONTAINER_ID psql -h localhost postgres judge -c \
    "UPDATE pg_database SET datallowconn = 'false' WHERE datname = 'judge';"

# Force disconnect all clients from the database using this command
docker exec -it $CONTAINER_ID psql -h localhost postgres judge -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'judge';"

# Delete the database
docker exec -it $CONTAINER_ID psql -h localhost postgres judge -c \
    "DROP DATABASE judge;"

# After deleting the `judge` database, we need to create a placeholder
# for the restore.
docker exec -it $CONTAINER_ID psql -h localhost postgres judge -c \
    "CREATE DATABASE judge OWNER judge;"

# Finally, restore the database from `judge.sql`
docker exec -i $CONTAINER_ID sh -c 'psql -U judge < /judge.sql'
```

## Backup

Make sure `backup.sh` is added as a cron job to run at least once a day:

```bash
(crontab -l 2>/dev/null; echo "0 0 * * * ~/judge/backup.sh") | crontab -
```