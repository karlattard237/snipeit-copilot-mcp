#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR=${SOURCE_DIR:-/opt/snipeit-copilot-mcp}
STATE_DIR=${STATE_DIR:-/var/lib/snipeit-copilot-mcp}
ENV_FILE=${ENV_FILE:-/etc/snipeit-copilot-mcp.env}
UNIT_FILE=${UNIT_FILE:-/etc/systemd/system/snipeit-copilot-mcp.service}
SERVICE_USER=snipeit-copilot-mcp
UV_BIN=${UV_BIN:-/usr/local/bin/uv}

die() { echo "setup: $*" >&2; exit 1; }
[[ ${EUID} -eq 0 ]] || die "run as root"
[[ -d ${SOURCE_DIR} && -f ${SOURCE_DIR}/pyproject.toml && -f ${SOURCE_DIR}/uv.lock ]] || die "SOURCE_DIR is not a project checkout"
[[ -x ${UV_BIN} ]] || die "install a trusted pinned uv binary at UV_BIN first"
command -v systemctl >/dev/null || die "systemd is required"

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home-dir "${STATE_DIR}" --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" -m 0700 "${STATE_DIR}"
chown -R root:root "${SOURCE_DIR}"
chmod -R go-w "${SOURCE_DIR}"

if [[ ! -f ${ENV_FILE} ]]; then
  install -o root -g "${SERVICE_USER}" -m 0640 "${SOURCE_DIR}/.env.example" "${ENV_FILE}"
  echo "setup: created ${ENV_FILE}; replace placeholders before starting" >&2
else
  chown root:"${SERVICE_USER}" "${ENV_FILE}"
  chmod 0640 "${ENV_FILE}"
fi

env HOME="${STATE_DIR}" UV_PROJECT_ENVIRONMENT="${SOURCE_DIR}/.venv" \
  "${UV_BIN}" sync --frozen --no-dev --no-editable --project "${SOURCE_DIR}"
chown -R root:root "${SOURCE_DIR}/.venv"
chmod -R go-w "${SOURCE_DIR}/.venv"

install -o root -g root -m 0644 "${SOURCE_DIR}/deploy/snipeit-copilot-mcp.service" "${UNIT_FILE}"
systemctl daemon-reload
systemctl enable snipeit-copilot-mcp.service

if grep -Eq '^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=.*(replace-with-|your-mcp-host|snipeit\.example\.com)' "${ENV_FILE}"; then
  echo "setup: service enabled but not started; edit ${ENV_FILE}, then run:" >&2
  echo "  systemctl start snipeit-copilot-mcp.service" >&2
  exit 0
fi

systemctl restart snipeit-copilot-mcp.service
echo "setup: service installed, enabled, and started" >&2
