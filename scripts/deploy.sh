#!/bin/bash

# Deploy Script
# Updates production to the latest master: the api, the nginx container and
# both graders. Run it on the production host, from inside the repository.
# Usage: ./scripts/deploy.sh
#        DEPLOY_BRANCH=my-branch ./scripts/deploy.sh   (to try out a branch)
#
# Steps:
#   1. Pull the latest master (fast-forward only).
#   2. Build the new api and grader images while everything keeps running.
#   3. With the new api image: apply migrations and collect static files.
#   4. Replace the api container (the site is down for a few seconds).
#   5. Recreate nginx, only if its config changed.
#   6. Replace the graders one at a time, so one is always grading. Each one
#      finishes the submission it is grading before it stops.

set -euo pipefail  # Exit on error, undefined variables, and pipe failures

# Configuration
BRANCH="${DEPLOY_BRANCH:-master}"
COMPOSE_FILE="docker/prod/docker-compose.yml"
# Existing volumes are named after this project (prod_varwww, prod_problems, ...)
COMPOSE_PROJECT="prod"
PYTHON="environ/bin/python3"
SITE_HOST="matcomgrader.com"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

compose() {
    docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" "$@"
}

# Make sure the checkout is clean, then bring it up to date
update_code() {
    if [[ "$(git rev-parse --abbrev-ref HEAD)" != "$BRANCH" ]]; then
        log_error "Not on '$BRANCH'; switch to it before deploying."
        exit 1
    fi
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
        log_error "There are uncommitted changes; commit or discard them first:"
        git status --short --untracked-files=no >&2
        exit 1
    fi
    log_info "Pulling latest '$BRANCH'..."
    git pull --ff-only origin "$BRANCH"
    log_info "Deploying $(git log -1 --format='%h %s')"
}

build_images() {
    log_info "Building api and grader images..."
    # grader-2 runs the image the grader service builds
    compose build api grader
}

# Runs before the api is replaced, so the new code finds its tables and its
# static files already in place. varwww is a named volume, which Docker never
# refreshes from the image, hence collectstatic on every deploy.
prepare_release() {
    log_info "Applying database migrations..."
    compose run --rm --no-deps api "$PYTHON" manage.py migrate --noinput
    log_info "Collecting static files..."
    compose run --rm --no-deps api "$PYTHON" manage.py collectstatic --noinput
}

deploy_api() {
    log_info "Replacing api container..."
    compose up -d --no-deps api
}

# nginx.conf is mounted as a single file. `git pull` replaces that file
# instead of editing it, and a running container keeps seeing the old one, so
# nginx must be recreated when its config changed.
deploy_nginx() {
    local previous="$1"
    if git diff --quiet "$previous" HEAD -- docker/prod/nginx.conf; then
        compose up -d --no-deps nginx
    else
        log_info "nginx.conf changed; recreating nginx..."
        compose up -d --no-deps --force-recreate nginx
    fi
}

# One at a time, so there is always a grader running. Stopping a grader waits
# for the submission it is grading (see StopRequest in grader.py).
deploy_graders() {
    for grader in grader grader-2; do
        log_info "Replacing $grader (waits for its current submission)..."
        compose up -d --no-deps "$grader"
    done
}

# The site answers through nginx on port 80 (Cloudflare redirects visitors to
# HTTPS; port 80 on the host still serves the site).
check_site() {
    local status
    log_info "Waiting for the site to answer..."
    for _ in $(seq 1 30); do
        status=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $SITE_HOST" http://127.0.0.1/ || true)
        if [[ "$status" == "200" ]]; then
            log_info "Site answered with HTTP 200."
            return 0
        fi
        sleep 2
    done
    log_error "Site did not answer with 200 (last status: ${status:-none})."
    log_error "Check the logs: docker compose -p $COMPOSE_PROJECT -f $COMPOSE_FILE logs api nginx"
    exit 1
}

main() {
    # Work from the repository root, wherever the script is called from
    cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

    local previous
    previous=$(git rev-parse HEAD)

    update_code
    build_images
    prepare_release
    deploy_api
    deploy_nginx "$previous"
    check_site
    deploy_graders

    # Old images are left dangling after each build
    docker image prune -f >/dev/null

    compose ps api nginx grader grader-2
    log_info "Deploy completed successfully!"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo "Usage: $0"
    echo "       DEPLOY_BRANCH=my-branch $0   (to try out a branch)"
    echo ""
    echo "Deploy the latest '$BRANCH' to production: api, nginx and graders."
    echo "Run it on the production host, inside the repository checkout."
    exit 0
fi

main "$@"
