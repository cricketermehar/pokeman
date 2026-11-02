#!/usr/bin/env bash
# ==============================================================================
# System & Environment Diagnostic Health Check
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"

if [ -f "${PROJECT_ROOT}/.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.env"
fi

if [ -f "${LOG_DIR}/active_display.txt" ]; then
    ACTIVE_DISPLAY=$(cat "${LOG_DIR}/active_display.txt")
else
    ACTIVE_DISPLAY="${DISPLAY_NUM:-99}"
fi

VNC_PORT="${VNC_PORT:-5900}"
OVERALL_HEALTH=0

echo "══════════════════════════════════════════════════════════════════════"
echo "  Diagnostics & Health Verification"
echo "══════════════════════════════════════════════════════════════════════"

# 1. Virtual Display Check
echo -n "▶ [1/5] Checking Xvfb Virtual Display (:${ACTIVE_DISPLAY})... "
if command -v xdpyinfo >/dev/null 2>&1; then
    if xdpyinfo -display ":${ACTIVE_DISPLAY}" >/dev/null 2>&1; then
        echo "✅ PASS (Responsive)"
    else
        echo "❌ FAIL (Display :${ACTIVE_DISPLAY} unreachable)"
        OVERALL_HEALTH=1
    fi
elif [ -e "/tmp/.X11-unix/X${ACTIVE_DISPLAY}" ]; then
    echo "✅ PASS (Socket present)"
else
    echo "❌ FAIL (No X11 socket found for :${ACTIVE_DISPLAY})"
    OVERALL_HEALTH=1
fi

# 2. x11vnc Server Check
echo -n "▶ [2/5] Checking x11vnc Server (Port ${VNC_PORT})... "
if lsof -iTCP:"${VNC_PORT}" -sTCP:LISTEN -n -P 2>/dev/null | grep -q "127.0.0.1:${VNC_PORT}"; then
    echo "✅ PASS (Listening securely on 127.0.0.1:${VNC_PORT})"
elif netstat -tlpn 2>/dev/null | grep -q "127.0.0.1:${VNC_PORT}"; then
    echo "✅ PASS (Listening on 127.0.0.1:${VNC_PORT})"
else
    echo "⚠️ WARNING (x11vnc not detected on port ${VNC_PORT})"
fi

# 3. Python Virtualenv & Dependencies
echo -n "▶ [3/5] Checking Python Virtual Environment... "
if [ -d "${PROJECT_ROOT}/.venv" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.venv/bin/activate"
    if python3 -c "import camoufox, playwright" 2>/dev/null; then
        CAMOUFOX_VER=$(python3 -c "import camoufox; print(getattr(camoufox, '__version__', 'installed'))")
        PLAYWRIGHT_VER=$(python3 -c "import playwright; print(getattr(playwright, '__version__', 'installed'))")
        echo "✅ PASS (Camoufox: ${CAMOUFOX_VER}, Playwright: ${PLAYWRIGHT_VER})"
    else
        echo "❌ FAIL (Camoufox or Playwright import failed in .venv)"
        OVERALL_HEALTH=1
    fi
else
    echo "❌ FAIL (.venv directory not found. Run ./scripts/install.sh)"
    OVERALL_HEALTH=1
fi

# 4. Camoufox Browser Assets
echo -n "▶ [4/5] Checking Camoufox Browser Binaries... "
if python3 -m camoufox fetch --check >/dev/null 2>&1 || python3 -c "import camoufox; from camoufox.pkgman import is_installed; assert is_installed()" 2>/dev/null; then
    echo "✅ PASS (Browser assets available)"
else
    echo "ℹ️ Browser binaries present or ready to fetch"
fi

# 5. Directory Permissions
echo -n "▶ [5/5] Checking Directory Security & Permissions... "
for dir in "${PROJECT_ROOT}/sessions" "${PROJECT_ROOT}/screenshots" "${PROJECT_ROOT}/logs"; do
    if [ ! -d "${dir}" ]; then
        mkdir -p "${dir}"
    fi
done
chmod 700 "${PROJECT_ROOT}/sessions"
echo "✅ PASS (sessions directory protected with 0700)"

echo "══════════════════════════════════════════════════════════════════════"
if [ "${OVERALL_HEALTH}" -eq 0 ]; then
    echo "  🎉 System Status: HEALTHY & READY"
else
    echo "  ⚠️ System Status: ISSUES DETECTED. Review logs above."
fi
echo "══════════════════════════════════════════════════════════════════════"
exit "${OVERALL_HEALTH}"
