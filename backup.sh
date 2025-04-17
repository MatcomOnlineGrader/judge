#!/usr/bin/env bash

# Set the path where Dropbox-Uploader is (or will be) installed
UPLOAD_DIR="/opt/Dropbox-Uploader"

sync_dropbox_uploader() {
    if [ ! -d "$UPLOAD_DIR/.git" ]; then
        git clone "git@github.com:andreafabrizi/Dropbox-Uploader.git" "$UPLOAD_DIR"
    else
        git -C "$UPLOAD_DIR" pull
    fi
}

# Prepare backup directory
rm -rf /opt/backup
mkdir -p /opt/backup

# Make sure Dropbox-Uploader is up to date
sync_dropbox_uploader

# Dump the PostgreSQL database to a file
docker exec $(docker ps --filter "name=database" --format "{{.ID}}") \
    pg_dump -U judge -d judge --no-owner >/opt/backup/judge.sql

# Backup media files from Docker volume
MEDIA_PATH=$(docker volume inspect prod_varwww --format '{{.Mountpoint}}')/media
tar czf /opt/backup/media.tar.gz -C $MEDIA_PATH .

# Backup problems tests from Docker volume
PROBLEMS_PATH=$(docker volume inspect prod_problems --format '{{.Mountpoint}}')
tar czf /opt/backup/problems.tar.gz -C $PROBLEMS_PATH .

# Use weekday number (1–7) to rotate backups
DAY=$(date +%u)

# Upload and replace each backup file in Dropbox
for FILE in judge.sql media.tar.gz problems.tar.gz; do
    REMOTE_NAME="${FILE/./.$DAY.}"
    $UPLOAD_DIR/dropbox_uploader.sh remove "/$REMOTE_NAME"
    $UPLOAD_DIR/dropbox_uploader.sh upload "/opt/backup/$FILE" "/$REMOTE_NAME"
done

# Clean up temporary backup files
rm -rf /opt/backup
