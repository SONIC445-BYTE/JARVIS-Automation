#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="jarvis-automation-daemon.service"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
SERVICE_PATH="${SYSTEMD_USER_DIR}/${SERVICE_NAME}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "${SYSTEMD_USER_DIR}"

cat > "${SERVICE_PATH}" <<EOF
[Unit]
Description=JARVIS Automation Daemon
After=network.target

[Service]
Type=simple
WorkingDirectory=${ROOT_DIR}
ExecStart=${PYTHON_BIN} -m daemon.cli run-loop
Restart=always
RestartSec=2
Environment=PYTHONPATH=${ROOT_DIR}

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "${SERVICE_NAME}"

cat > "${ROOT_DIR}/tools/rollback.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SERVICE_NAME="jarvis-automation-daemon.service"
SERVICE_PATH="${HOME}/.config/systemd/user/${SERVICE_NAME}"
systemctl --user disable --now "${SERVICE_NAME}" || true
rm -f "${SERVICE_PATH}"
systemctl --user daemon-reload
echo "Rollback complete."
EOF
chmod +x "${ROOT_DIR}/tools/rollback.sh"

echo "Installed ${SERVICE_NAME} (user systemd)."
echo "Rollback script created at tools/rollback.sh"
