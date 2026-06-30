#!/bin/bash
if [ ! -f "settings.ini" ]; then
  perl -pe 's/secret_auto_fillable_placeholder/substr("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",rand()*62,12)/ge' settings.ini.template > settings.ini
fi

database_pass=$(awk -F ":" '/DATABASE_PASS/ {gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2}' settings.ini)

# The grader image is x86_64-only (custom gcc 11.3.0 toolchain). On arm64 hosts
# (Apple Silicon) it must be cross-built as linux/amd64 under emulation, which
# requires BuildKit and the buildx plugin. Docker Desktop ships buildx; Homebrew
# installs it but doesn't register it as a Docker CLI plugin, so wire it up here.
if ! docker buildx version >/dev/null 2>&1; then
  brew_buildx="$(brew --prefix 2>/dev/null)/lib/docker/cli-plugins/docker-buildx"
  if [ -x "$brew_buildx" ]; then
    echo "Registering Homebrew's buildx as a Docker CLI plugin..."
    mkdir -p "$HOME/.docker/cli-plugins"
    ln -sf "$brew_buildx" "$HOME/.docker/cli-plugins/docker-buildx"
  else
    echo "ERROR: 'docker buildx' is required to build the grader image (linux/amd64)." >&2
    echo "Install it (macOS: 'brew install docker-buildx') or enable buildx in your Docker setup." >&2
    exit 1
  fi
fi

DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 DATABASE_PASS=$database_pass \
    docker-compose -f docker/dev/docker-compose.yml up
