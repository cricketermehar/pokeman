#!/usr/bin/env bash
# ==============================================================================
# Service Shutdown Script
# Terminates Xvfb, x11vnc, and cleans up resources cleanly.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"

terminate_process() {
    local name="$1"
    local pid_file="$2"

    if [ -f "${pid_file}" ]; then
        local pid
        pid=$(cat "${pid_file}" || true)
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            echo "▶ Stopping ${name} (PID: ${pid})..."
            kill -15 "${pid}" 2>/dev/null || true
            for i in {1..20}; do
                if ! kill -0 "${pid}" 2>/dev/null; then
                    break
                fi
                sleep 0.1
            done
            if kill -0 "${pid}" 2>/dev/null; then
                echo "  ⚠️ ${name} did not stop gracefully; sending SIGKILL..."
                kill -9 "${pid}" 2>/dev/null || true
            fi
            echo "  ✅ ${name} stopped."
        fi
        rm -f "${pid_file}"
    fi
}

echo "══════════════════════════════════════════════════════════════════════"
echo "  Shutting Down Camoufox Automation Display & VNC Services"
echo "══════════════════════════════════════════════════════════════════════"

# 1. Stop x11vnc
terminate_process "x11vnc" "${LOG_DIR}/x11vnc.pid"

# 2. Stop window manager
terminate_process "fluxbox" "${LOG_DIR}/wm.pid"

# 3. Stop Xvfb
terminate_process "Xvfb" "${LOG_DIR}/xvfb.pid"

# 4. Clean up stale X11 sockets
if [ -f "${LOG_DIR}/active_display.txt" ]; then
    ACTIVE_DISPLAY=$(cat "${LOG_DIR}/active_display.txt")
    if [ -n "${ACTIVE_DISPLAY}" ]; then
        echo "▶ Cleaning X11 lock files for :${ACTIVE_DISPLAY}..."
        rm -f "/tmp/.X${ACTIVE_DISPLAY}-lock" "/tmp/.X11-unix/X${ACTIVE_DISPLAY}"
    fi
    rm -f "${LOG_DIR}/active_display.txt"
fi

echo "  ✅ All virtual display and remote desktop services stopped cleanly."
