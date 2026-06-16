#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

GATEWAY_PORT=8001
FRONTEND_PORT=3000
NGINX_PORT=8080
MODE="dev"
STOP_ONLY=false

# ── Parse args ─────────────────────────────────────────────────────────────
for arg in "$@"; do
    case $arg in
        --dev)   MODE="dev"  ;;
        --prod)  MODE="prod" ;;
        --stop)  STOP_ONLY=true ;;
    esac
done

# ── Stop all services ──────────────────────────────────────────────────────
stop_all() {
    echo "Stopping services..."
    pkill -f "uvicorn ai_research_engineer.server.app:app" 2>/dev/null || true
    pkill -f "next dev"   2>/dev/null || true
    pkill -f "next start" 2>/dev/null || true
    nginx -s quit         2>/dev/null || true
    # Free the ports to be sure
    for port in $GATEWAY_PORT $FRONTEND_PORT $NGINX_PORT; do
        lsof -ti ":$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
    done
}

if $STOP_ONLY; then
    stop_all
    echo "Done."
    exit 0
fi

# ── Cleanup on Ctrl-C ──────────────────────────────────────────────────────
trap 'echo; stop_all; exit 0' INT TERM

# ── Pre-flight ────────────────────────────────────────────────────────────
stop_all; sleep 1

if ! command -v nginx &>/dev/null; then
    echo "⚠  nginx not found. Install it with: brew install nginx"
    echo "   Running without nginx — gateway :$GATEWAY_PORT, frontend :$FRONTEND_PORT"
    SKIP_NGINX=true
else
    SKIP_NGINX=false
fi

if [ ! -f .env ]; then
    echo "⚠  .env not found. Copy .env.example and fill in your keys."
    echo "   cp .env.example .env"
fi

# ── Install deps ──────────────────────────────────────────────────────────
echo "Syncing dependencies..."
uv sync --quiet
(cd frontend && npm install --silent)

mkdir -p logs .data

# ── Start gateway ─────────────────────────────────────────────────────────
echo
echo "Starting gateway..."
GATEWAY_CMD="PYTHONPATH=src uv run uvicorn ai_research_engineer.server.app:app --host 0.0.0.0 --port $GATEWAY_PORT"
bash -c "$GATEWAY_CMD" > logs/gateway.log 2>&1 &

./scripts/wait-for-port.sh $GATEWAY_PORT 30 "Gateway"

# ── Start frontend ────────────────────────────────────────────────────────
echo "Starting frontend..."
if [ "$MODE" = "prod" ]; then
    FRONTEND_CMD="npm run build && npm start"
else
    FRONTEND_CMD="npm run dev"
fi
(cd frontend && bash -c "$FRONTEND_CMD") > logs/frontend.log 2>&1 &

./scripts/wait-for-port.sh $FRONTEND_PORT 120 "Frontend"

# ── Start nginx ───────────────────────────────────────────────────────────
if ! $SKIP_NGINX; then
    echo "Starting nginx..."
    nginx -g 'daemon off;' -c "$REPO_ROOT/docker/nginx/nginx.local.conf" -p "$REPO_ROOT" > logs/nginx.log 2>&1 &
    ./scripts/wait-for-port.sh $NGINX_PORT 10 "Nginx"
fi

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ! $SKIP_NGINX; then
    echo "  App:     http://localhost:$NGINX_PORT"
fi
echo "  Gateway: http://localhost:$GATEWAY_PORT"
echo "  Frontend: http://localhost:$FRONTEND_PORT"
echo "  Logs:    ./logs/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Press Ctrl-C to stop all services"
echo

wait
