#!/usr/bin/env bash
# ==============================================================================
# Secure Remote Desktop (x11vnc) Manager
# Binds strictly to 127.0.0.1 and enforces password authentication.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"

if [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
fi

VNC_PORT="${VNC_PORT:-5900}"
VNC_PASSWD="${VNC_PASSWD_FILE:-${HOME}/.vnc/passwd}"
VNC_PID_FILE="${LOG_DIR}/x11vnc.pid"
VNC_LOG="${LOG_DIR}/x11vnc.log"

# Read active display number
if [ -f "${LOG_DIR}/active_display.txt" ]; then
    ACTIVE_DISPLAY=$(cat "${LOG_DIR}/active_display.txt")
else
    ACTIVE_DISPLAY="${DISPLAY_NUM:-99}"
fi

echo "══════════════════════════════════════════════════════════════════════"
echo "  Starting Secure x11vnc Server"
echo "══════════════════════════════════════════════════════════════════════"

# 1. Verify Xvfb display is active
if ! xdpyinfo -display ":${ACTIVE_DISPLAY}" >/dev/null 2>&1 && [ ! -e "/tmp/.X11-unix/X${ACTIVE_DISPLAY}" ]; then
    echo "❌ Error: Xvfb display :${ACTIVE_DISPLAY} is not running." >&2
    echo "   Run ./scripts/start_display.sh first." >&2
    exit 1
fi

# 2. Verify VNC password file
if [ ! -f "${VNC_PASSWD}" ]; then
    echo "⚠️ Warning: VNC password file not found at ${VNC_PASSWD}. Creating one..."
    mkdir -p "$(dirname "${VNC_PASSWD}")"
    chmod 700 "$(dirname "${VNC_PASSWD}")"
    echo "secret123" | x11vnc -storepasswd "secret123" "${VNC_PASSWD}"
    chmod 600 "${VNC_PASSWD}"
    echo "  🔑 Default temporary password set to: secret123"
fi

# 3. Check if already running
if [ -f "${VNC_PID_FILE}" ]; then
    EXISTING_PID=$(cat "${VNC_PID_FILE}" || true)
    if [ -n "${EXISTING_PID}" ] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
        echo "ℹ️ x11vnc is already running with PID ${EXISTING_PID} on port ${VNC_PORT}"
        exit 0
    else
        rm -f "${VNC_PID_FILE}"
    fi
fi

# 4. Launch x11vnc with strict security:
# - -localhost: Binds ONLY to 127.0.0.1 (never open to public WAN)
# - -rfbauth: Requires encrypted password authentication
# - -forever: Keeps listening across client disconnects
# - -shared: Allows seamless reconnection
# - -rfbport: Port configuration
echo "▶ Launching x11vnc attached to :${ACTIVE_DISPLAY} on 127.0.0.1:${VNC_PORT}..."
x11vnc \
    -display ":${ACTIVE_DISPLAY}" \
    -localhost \
    -rfbauth "${VNC_PASSWD}" \
    -rfbport "${VNC_PORT}" \
    -shared \
    -forever \
    -bg \
    -o "${VNC_LOG}"

# Extract PID from log or pgrep
sleep 1
VNC_PID=$(pgrep -f "x11vnc.*${ACTIVE_DISPLAY}" | head -n 1 || true)
if [ -n "${VNC_PID}" ]; then
    echo "${VNC_PID}" > "${VNC_PID_FILE}"
    echo "  ✅ x11vnc started successfully (PID: ${VNC_PID})"
else
    echo "❌ Error: x11vnc process could not be confirmed. Check ${VNC_LOG}" >&2
    exit 1
fi

echo "══════════════════════════════════════════════════════════════════════"
echo "  🔒 SECURE REMOTE ACCESS (SSH TUNNELING)"
echo "══════════════════════════════════════════════════════════════════════"
echo "The VNC server is locked to localhost and CANNOT be accessed directly."
echo ""
echo "To connect securely from your local workstation:"
echo "1. Run this SSH tunnel command on your local machine:"
echo "   ssh -N -L 5900:127.0.0.1:${VNC_PORT} user@YOUR_SERVER_IP"
echo ""
echo "2. Open your VNC client (e.g. TigerVNC, RealVNC, or macOS Screen Sharing):"
echo "   Connect to: vnc://localhost:5900"
echo "   Enter your VNC password."
echo ""
echo "3. To close the SSH tunnel when finished:"
echo "   Press Ctrl+C in the SSH terminal or kill the ssh process."
echo "══════════════════════════════════════════════════════════════════════"
