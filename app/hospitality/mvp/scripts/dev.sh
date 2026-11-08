#!/usr/bin/env bash

trap 'kill 0' EXIT

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Load NVM if available (ensures correct Node version)
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

# ── Read ports from .ttest/config.yaml using python (reliable YAML parsing) ──
BE_PORT=8000
FE_PORT=3100

if [ -f ".ttest/config.yaml" ]; then
  read -r BE_PORT FE_PORT < <(python3 -c "
import yaml, sys
with open('.ttest/config.yaml') as f:
    cfg = yaml.safe_load(f)
services = cfg.get('run', {}).get('services', [])
be = next((s['port'] for s in services if s.get('name') == 'backend'), 8000)
fe = next((s['port'] for s in services if s.get('name') == 'frontend'), 3100)
print(be, fe)
" 2>/dev/null || echo "$BE_PORT $FE_PORT")
fi

# ── Create .env from example if missing ──
# Both backend/.env (pydantic-settings) and frontend/.env.local (Next.js) need
# their own copy — Next.js only ever reads .env* files from its own cwd
# (frontend/), never from the workspace root .env.example.
if [ ! -f "backend/.env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example backend/.env
    echo "  Created backend/.env from .env.example"
  fi
fi

if [ ! -f "frontend/.env.local" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example frontend/.env.local
    echo "  Created frontend/.env.local from .env.example"
  fi
fi

# ── Backend setup ──
echo "=== Backend (FastAPI) on port $BE_PORT ==="
cd "$ROOT/backend"

if [ ! -d ".venv" ]; then
  echo "  Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "  Installing dependencies..."
  if [ -f constraints.txt ]; then
    constraints="$ROOT/backend/constraints.txt"
    if (LC_ALL=C; case "$constraints" in *[!!-~]*) exit 0 ;; esac; exit 1); then
      echo "  WARNING: the path to backend/constraints.txt contains whitespace or a character outside printable ASCII, so pip gets the relative path constraints.txt" >&2; constraints=constraints.txt
    fi
    PIP_CONSTRAINT="$constraints" PIP_BUILD_CONSTRAINT="$constraints" pip install -e "." --quiet
  else
    pip install -e "." --quiet
  fi
fi

echo "  Starting..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$BE_PORT" --reload &

# ── Frontend setup ──
echo "=== Frontend (Next.js) on port $FE_PORT ==="
cd "$ROOT/frontend"

if [ ! -x "node_modules/.bin/next" ]; then
  echo "  Installing dependencies..."
  if ! npm install; then
    echo "  [WARN] npm install failed, retrying with --legacy-peer-deps..."
    npm install --legacy-peer-deps
  fi
fi

echo "  Starting..."
npm run dev -- -p "$FE_PORT" &

echo ""
echo "=== Both servers running ==="
echo "  Backend:  http://localhost:$BE_PORT"
echo "  Frontend: http://localhost:$FE_PORT"
echo ""
echo "Press Ctrl+C to stop both."

wait
