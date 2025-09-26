#!/bin/bash

# Database and Media Restore Script
# This script restores a PostgreSQL database and media files to Docker containers
# Usage: ./restore_script.sh [FOLDER_PATH]
# Example: ./restore_script.sh ~/Downloads

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Configuration
DB_CONTAINER_NAME="dev_database"
API_CONTAINER_NAME="dev_api"
DB_NAME="judge"
DB_USER="judge"
SQL_FILE="judge.sql"
MEDIA_FILE="media.tar.gz"
PROBLEMS_FILE="problems.tar.gz"

# Get folder path from command line argument or use current directory
RESTORE_FOLDER="${1:-.}"

# Expand tilde to home directory if present
RESTORE_FOLDER="${RESTORE_FOLDER/#\~/$HOME}"

# Convert to absolute path
RESTORE_FOLDER=$(realpath "$RESTORE_FOLDER")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if file exists in the restore folder
check_file_exists() {
    local filename="$1"
    local filepath="$RESTORE_FOLDER/$filename"
    
    if [[ ! -f "$filepath" ]]; then
        log_error "Required file '$filename' not found in '$RESTORE_FOLDER'!"
        log_error "Expected path: $filepath"
        exit 1
    fi
    
    log_info "Found file: $filepath"
}

# Function to get container ID
get_container_id() {
    local container_name="$1"
    local container_id
    
    container_id=$(docker ps -q --filter "name=$container_name" 2>/dev/null)
    
    if [[ -z "$container_id" ]]; then
        log_error "Container '$container_name' not found or not running!"
        exit 1
    fi
    
    echo "$container_id"
}

# Function to execute PostgreSQL command
execute_psql() {
    local container_id="$1"
    local command="$2"
    local database="${3:-postgres}"
    
    docker exec -i "$container_id" psql -h localhost -U $DB_USER -d "$database" -c "$command"
}

# Function to restore database
restore_database() {
    local container_id="$1"
    local sql_path="$RESTORE_FOLDER/$SQL_FILE"
    
    log_info "Starting database restoration process..."
    
    # Check if SQL file exists
    check_file_exists "$SQL_FILE"
    
    # Copy SQL file to container
    log_info "Copying $SQL_FILE to container..."
    docker cp "$sql_path" "$container_id:/"
    
    # Disconnect all clients and drop database
    log_info "Disconnecting clients from database '$DB_NAME'..."
    execute_psql "$container_id" \
        "UPDATE pg_database SET datallowconn = 'false' WHERE datname = '$DB_NAME';" \
        "postgres" || log_warn "Could not prevent new connections (database might not exist)"
    
    execute_psql "$container_id" \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" \
        "postgres" || log_warn "Could not terminate existing connections"
    
    # Drop and recreate database
    log_info "Dropping existing database '$DB_NAME'..."
    execute_psql "$container_id" "DROP DATABASE IF EXISTS $DB_NAME;" "postgres"
    
    log_info "Creating new database '$DB_NAME'..."
    execute_psql "$container_id" "CREATE DATABASE $DB_NAME OWNER $DB_USER;" "postgres"
    
    # Restore database from SQL file
    log_info "Restoring database from $SQL_FILE..."
    docker exec -i "$container_id" sh -c "psql -U $DB_USER -d $DB_NAME < /$SQL_FILE"
    
    # Clean up SQL file from container
    docker exec "$container_id" rm "/$SQL_FILE"
    
    log_info "Database restoration completed successfully!"
}

# Function to restore media files
restore_media() {
    local container_id="$1"
    local media_path="$RESTORE_FOLDER/$MEDIA_FILE"
    
    log_info "Starting media files restoration..."
    
    # Check if media file exists
    check_file_exists "$MEDIA_FILE"
    
    # Copy and extract media files
    log_info "Copying and extracting $MEDIA_FILE..."
    docker cp "$media_path" "$container_id:/var/www/judge/"
    docker exec "$container_id" tar -xzf "/var/www/judge/$MEDIA_FILE" -C /var/www/judge/media
    docker exec "$container_id" rm "/var/www/judge/$MEDIA_FILE"
    
    log_info "Media files restoration completed!"
}

# Function to restore problems
restore_problems() {
    local container_id="$1"
    local problems_path="$RESTORE_FOLDER/$PROBLEMS_FILE"
    
    log_info "Starting problems restoration..."
    
    # Check if problems file exists
    check_file_exists "$PROBLEMS_FILE"
    
    # Copy and extract problems
    log_info "Copying and extracting $PROBLEMS_FILE..."
    docker cp "$problems_path" "$container_id:/"
    docker exec "$container_id" tar -xzf "/$PROBLEMS_FILE" -C /problems
    docker exec "$container_id" rm "/$PROBLEMS_FILE"
    
    log_info "Problems restoration completed!"
}

# Main execution
main() {
    log_info "Starting restoration process..."
    log_info "Using restore folder: $RESTORE_FOLDER"
    
    # Check if restore folder exists
    if [[ ! -d "$RESTORE_FOLDER" ]]; then
        log_error "Restore folder '$RESTORE_FOLDER' does not exist!"
        exit 1
    fi
    
    # Get container IDs
    DB_CONTAINER_ID=$(get_container_id "$DB_CONTAINER_NAME")
    API_CONTAINER_ID=$(get_container_id "$API_CONTAINER_NAME")
    
    log_info "Found database container: $DB_CONTAINER_ID"
    log_info "Found API container: $API_CONTAINER_ID"
    
    # Restore database
    restore_database "$DB_CONTAINER_ID"
    
    # Restore media and problems
    restore_media "$API_CONTAINER_ID"
    restore_problems "$API_CONTAINER_ID"
    
    log_info "All restoration tasks completed successfully!"
}

# Show usage if help is requested
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0 [FOLDER_PATH]"
    echo ""
    echo "Restore database and media files from the specified folder."
    echo ""
    echo "Arguments:"
    echo "  FOLDER_PATH    Path to folder containing restore files (default: current directory)"
    echo ""
    echo "Required files in folder:"
    echo "  - $SQL_FILE"
    echo "  - $MEDIA_FILE" 
    echo "  - $PROBLEMS_FILE"
    echo ""
    echo "Examples:"
    echo "  $0                    # Use current directory"
    echo "  $0 ~/Downloads        # Use Downloads folder"
    echo "  $0 /path/to/backups   # Use specific path"
    exit 0
fi

# Run main function
main "$@"