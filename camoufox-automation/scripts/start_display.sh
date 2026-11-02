#!/usr/bin/env bash
# ==============================================================================
# Xvfb Virtual X11 Display Manager
# Starts a virtual framebuffer display with dynamic port conflict resolution.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"

# Load configuration if available
if [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
fi

REQUESTED_DISPLAY="${DISPLAY_NUM:-99}"
WIDTH="${SCREEN_WIDTH:-1920}"
HEIGHT="${SCREEN_HEIGHT:-1080}"
DEPTH="${SCREEN_DEPTH:-24}"
XVFB_PID_FILE="${LOG_DIR}/xvfb.pid"
XVFB_LOG="${LOG_DIR}/xvfb.log"
WM_PID_FILE="${LOG_DIR}/wm.pid"

is_display_in_use() {
    local disp="$1"
    # Check X11 unix socket
    if [ -e "/tmp/.X11-unix/X${disp}" ] || [ -e "/tmp/.X${disp}-lock" ]; then
        return 0
    fi
    # Check if xdpyinfo can query it
    if command -v xdpyinfo >/dev/null 2>&1; then
        if xdpyinfo -display ":${disp}" >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

find_free_display() {
    local disp="$1"
    while is_display_in_use "${disp}"; do
        echo "  ⚠️ Display :${disp} is occupied. Checking next display..." >&2
        disp=$((disp + 1))
    done
    echo "${disp}"
}

echo "══════════════════════════════════════════════════════════════════════"
echo "  Starting Xvfb Virtual Display"
echo "══════════════════════════════════════════════════════════════════════"

# Check if already running from PID file
if [ -f "${XVFB_PID_FILE}" ]; then
    EXISTING_PID=$(cat "${XVFB_PID_FILE}" || true)
    if [ -n "${EXISTING_PID}" ] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
        echo "ℹ️ Xvfb is already running with PID ${EXISTING_PID} on :$(cat "${LOG_DIR}/active_display.txt" 2>/dev/null || echo "${REQUESTED_DISPLAY}")"
        exit 0
    else
        rm -f "${XVFB_PID_FILE}"
    fi
fi

# Detect free display
ACTIVE_DISPLAY=$(find_free_display "${REQUESTED_DISPLAY}")
echo "▶ Using virtual display :${ACTIVE_DISPLAY} (${WIDTH}x${HEIGHT}x${DEPTH})"

# Clean up stale locks for the target display if process doesn't exist
if [ -e "/tmp/.X${ACTIVE_DISPLAY}-lock" ]; then
    LOCK_PID=$(cat "/tmp/.X${ACTIVE_DISPLAY}-lock" 2>/dev/null | tr -d ' ' || true)
    if [ -n "${LOCK_PID}" ] && ! kill -0 "${LOCK_PID}" 2>/dev/null; then
        echo "  🧹 Cleaning up stale lock file for :${ACTIVE_DISPLAY}"
        rm -f "/tmp/.X${ACTIVE_DISPLAY}-lock" "/tmp/.X11-unix/X${ACTIVE_DISPLAY}"
    fi
fi

# Launch Xvfb
# -nolisten tcp prevents public X11 socket exposure
Xvfb ":${ACTIVE_DISPLAY}" \
    -screen 0 "${WIDTH}x${HEIGHT}x${DEPTH}" \
    -nolisten tcp \
    -ac \
    +extension GLX \
    +render \
    -noreset \
    >"${XVFB_LOG}" 2>&1 &

XVFB_PID=$!
echo "${XVFB_PID}" > "${XVFB_PID_FILE}"
echo "${ACTIVE_DISPLAY}" > "${LOG_DIR}/active_display.txt"

# Validate that Xvfb is responding
echo "▶ Validating display readiness..."
SUCCESS=0
for i in {1..30}; do
    if kill -0 "${XVFB_PID}" 2>/dev/null; then
        if command -v xdpyinfo >/dev/null 2>&1; then
            if xdpyinfo -display ":${ACTIVE_DISPLAY}" >/dev/null 2>&1; then
                SUCCESS=1
                break
            fi
        else
            # If xdpyinfo not installed, check socket
            if [ -e "/tmp/.X11-unix/X${ACTIVE_DISPLAY}" ]; then
                SUCCESS=1
                break
            fi
        fi
    fi
    sleep 0.2
done

if [ "${SUCCESS}" -ne 1 ]; then
    echo "❌ Error: Xvfb failed to start within timeout. Check ${XVFB_LOG} for details." >&2
    exit 1
fi

# Optional: Start lightweight window manager for clean window management during VNC sessions
if command -v fluxbox >/dev/null 2>&1; then
    DISPLAY=":${ACTIVE_DISPLAY}" fluxbox >/dev/null 2>&1 &
    echo $! > "${WM_PID_FILE}"
fi

echo "  ✅ Xvfb running successfully on display :${ACTIVE_DISPLAY} (PID: ${XVFB_PID})"
echo "  To use in shell: export DISPLAY=:${ACTIVE_DISPLAY}"
