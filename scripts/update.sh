#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR=${SOURCE_DIR:-/opt/snipeit-copilot-mcp}
STATE_DIR=${STATE_DIR:-/var/lib/snipeit-copilot-mcp}
SERVICE_USER=snipeit-copilot-mcp
UV_BIN=${UV_BIN:-/usr/local/bin/uv}

die() { echo "update: $*" >&2; exit 1; }
[[ ${EUID} -eq 0 ]] || die "run as root"
[[ -d ${SOURCE_DIR}/.git ]] || die "SOURCE_DIR is not a git checkout"
[[ -x ${UV_BIN} ]] || die "uv is not installed at UV_BIN"

branch=$(git -C "${SOURCE_DIR}" symbolic-ref --quiet --short HEAD) || die "checkout must be on a named branch"
git -C "${SOURCE_DIR}" fetch --quiet origin "${branch}"
git -C "${SOURCE_DIR}" merge --ff-only "origin/${branch}"
chown -R root:root "${SOURCE_DIR}"
chmod -R go-w "${SOURCE_DIR}"

# Resolve and install the locked environment before taking the healthy service
# down. A dependency or build failure therefore leaves the current process up.
env HOME="${STATE_DIR}" UV_PROJECT_ENVIRONMENT="${SOURCE_DIR}/.venv" \
  "${UV_BIN}" sync --frozen --no-dev --no-editable --project "${SOURCE_DIR}"
chown -R root:root "${SOURCE_DIR}/.venv"
chmod -R go-w "${SOURCE_DIR}/.venv"
systemctl restart snipeit-copilot-mcp.service

for _ in $(seq 1 15); do
  if curl --fail --silent --max-time 2 http://127.0.0.1:8000/health >/dev/null; then
    echo "update: service is healthy" >&2
    exit 0
  fi
  sleep 1
done
die "service did not become healthy; inspect journalctl -u snipeit-copilot-mcp"
