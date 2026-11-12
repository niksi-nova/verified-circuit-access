#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

port="${PORT:-3000}"
engine_pid=
web_pid=
cleanup() {
  if [[ -n "$web_pid" ]]; then kill "$web_pid" 2>/dev/null || true; fi
  if [[ -n "$engine_pid" ]]; then kill "$engine_pid" 2>/dev/null || true; fi
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ ! -f web/.next/BUILD_ID ]]; then
  echo 'Build the frontend first with: npm --prefix web run build' >&2
  exit 1
fi
for local_port in 8000 "$port"; do
  if lsof -nP -iTCP:"$local_port" -sTCP:LISTEN 2>/dev/null | grep -q "IPv4"; then
    echo "Port $local_port is already in use. Stop the existing listener and retry." >&2
    exit 1
  fi
done

uv run --locked --offline --extra train --extra api python scripts/serve_api.py &
engine_pid=$!
(
  cd web
  exec node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port "$port"
) &
web_pid=$!

for ((i=0; i<120; i++)); do
  kill -0 "$engine_pid"
  kill -0 "$web_pid"
  if health=$(curl -fsS --max-time 1 http://127.0.0.1:8000/api/health 2>/dev/null); then
    if [[ "$health" == *'"engine_ready":true'* ]] &&
      curl -fsS --max-time 1 "http://127.0.0.1:$port/" >/dev/null 2>&1; then
      printf 'Braille Press is ready at http://127.0.0.1:%s\n' "$port"
      while kill -0 "$engine_pid" && kill -0 "$web_pid"; do sleep 1; done
      exit 1
    fi
    if [[ "$health" == *'"status":"offline"'* ]]; then
      printf 'The analysis engine could not start. %s\n' "$health" >&2
      exit 1
    fi
  fi
  sleep 1
done
echo 'Timed out waiting for the demo to start.' >&2
exit 1
