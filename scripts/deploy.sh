#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
    echo "Error: .env not found. Copy .env.example and fill in your keys."
    echo "  cp .env.example .env"
    exit 1
fi

export DATA_DIR="$REPO_ROOT/.data"
mkdir -p "$DATA_DIR"

echo "Building and starting Docker stack..."
docker compose -f docker/docker-compose.yaml up --build -d

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  App: http://localhost:8080"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  docker compose -f docker/docker-compose.yaml logs -f"
