#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
    set +a
fi

VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
PYTHON="${PYTHON:-$VENV_DIR/bin/python3}"
BACKEND_PORT="${BACKEND_PORT:-8001}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[bilun]${NC} $*"; }
warn() { echo -e "${YELLOW}[bilun]${NC} $*"; }
err()  { echo -e "${RED}[bilun]${NC} $*"; }

pids_on_port() {
    local port="$1"
    if command -v lsof &>/dev/null; then
        lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null || true
        return 0
    fi
    if command -v fuser &>/dev/null; then
        fuser -n tcp "$port" 2>/dev/null | tr ' ' '\n' || true
        return 0
    fi
    if command -v ss &>/dev/null; then
        ss -ltnp "sport = :$port" 2>/dev/null \
            | grep -oE 'pid=[0-9]+' \
            | cut -d= -f2 \
            | sort -u || true
    fi
}

free_port() {
    local port="$1"
    local label="${2:-port $port}"
    local pids=""

    mapfile -t pids < <(pids_on_port "$port" | sort -u)
    if [ "${#pids[@]}" -eq 0 ] || [ -z "${pids[0]:-}" ]; then
        return 0
    fi

    warn "Freeing $label (port $port) — stopping PID(s): ${pids[*]}"
    kill "${pids[@]}" 2>/dev/null || true
    sleep 1

    mapfile -t pids < <(pids_on_port "$port" | sort -u)
    if [ "${#pids[@]}" -gt 0 ] && [ -n "${pids[0]:-}" ]; then
        warn "Port $port still in use — sending SIGKILL to PID(s): ${pids[*]}"
        kill -9 "${pids[@]}" 2>/dev/null || true
        sleep 0.5
    fi
}

free_bilun_ports() {
    local target="${1:-all}"
    case "$target" in
        backend)
            free_port "$BACKEND_PORT" "backend"
            ;;
        frontend)
            free_port "$FRONTEND_PORT" "frontend"
            ;;
        all)
            free_port "$BACKEND_PORT" "backend"
            free_port "$FRONTEND_PORT" "frontend"
            ;;
    esac
}

ensure_pip() {
    if ! python3 -m pip --version &>/dev/null; then
        log "pip not found — bootstrapping via ensurepip..."
        python3 -m ensurepip --upgrade
    fi
}

ensure_venv() {
    if [ ! -f "$PYTHON" ]; then
        log "Creating virtual environment at $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
    fi
}

ensure_python_deps() {
    ensure_pip
    ensure_venv
    log "Installing/updating Python dependencies..."
    "$PYTHON" -m pip install -q -r requirements.txt
}

ensure_node() {
    if command -v node &>/dev/null; then
        return 0
    fi
    for dir in "$HOME"/.local/node-*-linux-x64/bin; do
        if [ -x "$dir/node" ]; then
            export PATH="$dir:$PATH"
            return 0
        fi
    done
    if [ -f "$NVM_DIR/nvm.sh" ]; then
        log "Loading nvm..."
        . "$NVM_DIR/nvm.sh"
        if command -v node &>/dev/null; then
            return 0
        fi
        log "Installing Node.js via nvm..."
        nvm install --lts
        nvm use --lts
        return 0
    fi
    err "Node.js not found and nvm not available at $NVM_DIR"
    err "Install Node.js: https://nodejs.org/"
    return 1
}

ensure_npm_deps() {
    if [ -f frontend/node_modules/.package-lock.json ]; then
        return 0
    fi
    log "Installing frontend dependencies..."
    pushd frontend > /dev/null
    npm install
    popd > /dev/null
}

start_backend() {
    free_bilun_ports backend
    ensure_python_deps
    log "Starting backend on port $BACKEND_PORT..."
    export BILUN_STARTUP_POLICY="${BILUN_STARTUP_POLICY:-load-only}"
    "$PYTHON" -m uvicorn src.bilun.api:app --host 0.0.0.0 --port "$BACKEND_PORT"
}

start_frontend() {
    free_bilun_ports frontend
    ensure_node || return 1
    ensure_npm_deps
    log "Starting frontend on port $FRONTEND_PORT..."
    pushd frontend > /dev/null
    npm run dev -- -p "$FRONTEND_PORT"
    popd > /dev/null
}

case "${1:-all}" in
    backend)
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
    all)
        free_bilun_ports all
        log "Starting backend in background..."
        start_backend &
        BACKEND_PID=$!
        sleep 3

        if ensure_node 2>/dev/null; then
            free_bilun_ports frontend
            ensure_npm_deps
            log "Starting frontend on port $FRONTEND_PORT..."
            pushd frontend > /dev/null
            npm run dev -- -p "$FRONTEND_PORT" &
            FRONTEND_PID=$!
            popd > /dev/null
        else
            warn "Frontend not available — backend running at http://localhost:$BACKEND_PORT"
            FRONTEND_PID=""
        fi

        cleanup() {
            kill $BACKEND_PID ${FRONTEND_PID:-} 2>/dev/null || true
            free_bilun_ports all
        }
        trap cleanup INT TERM
        wait
        ;;
    *)
        echo "Usage: $0 {backend|frontend|all}"
        exit 1
        ;;
esac
