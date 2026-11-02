#!/usr/bin/env bash
# ==============================================================================
# Linux Environment Setup Script for Camoufox + Playwright + Xvfb + x11vnc
# Targeted for: Ubuntu 22.04 / 24.04 LTS
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "══════════════════════════════════════════════════════════════════════"
echo "  Camoufox + Playwright + Xvfb Linux Setup"
echo "══════════════════════════════════════════════════════════════════════"

# 1. Root Check / Sudo validation
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "❌ Error: sudo is required to install system packages." >&2
        exit 1
    fi
fi

# 2. Install Linux System Packages
echo "▶ [1/5] Updating package cache and installing X11/VNC dependencies..."
$SUDO apt-get update -y
$SUDO apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    x11-utils \
    lsof \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libgtk-3-0 \
    libasound2 \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    openssh-server

echo "  ✅ System dependencies installed successfully."

# 3. Python Virtual Environment Setup
echo "▶ [2/5] Creating Python virtual environment in .venv..."
cd "${PROJECT_ROOT}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

# 4. Install Python Dependencies
echo "▶ [3/5] Installing Camoufox (0.5.6) and Playwright (1.62.0)..."
pip install -r requirements.txt

# 5. Fetch Camoufox Browser Assets
echo "▶ [4/5] Fetching Camoufox customized Firefox browser binaries..."
python3 -m camoufox fetch

# 6. Configure Secure VNC Password Store
echo "▶ [5/5] Configuring x11vnc authentication password..."
mkdir -p "${HOME}/.vnc"
chmod 700 "${HOME}/.vnc"

VNC_PASSWD_PATH="${HOME}/.vnc/passwd"
if [ ! -f "${VNC_PASSWD_PATH}" ]; then
    # Generate a random 12-char password if non-interactive, or prompt
    if [ -t 0 ]; then
        echo "Enter a secure VNC password when prompted:"
        x11vnc -storepasswd "${VNC_PASSWD_PATH}"
    else
        RAND_PASS=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 12 || true)
        echo "${RAND_PASS}" | x11vnc -storepasswd "${RAND_PASS}" "${VNC_PASSWD_PATH}"
        echo "  🔑 Generated non-interactive VNC password: ${RAND_PASS}"
    fi
    chmod 600 "${VNC_PASSWD_PATH}"
else
    echo "  ℹ️ Existing VNC password file found at ${VNC_PASSWD_PATH}"
fi

# Ensure default environment file exists
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ℹ️ Created initial .env configuration from .env.example"
fi

echo "══════════════════════════════════════════════════════════════════════"
echo "  ✅ Installation and Environment Verification Complete!"
echo "══════════════════════════════════════════════════════════════════════"
echo "Next steps:"
echo "  1. Start virtual display : ./scripts/start_display.sh"
echo "  2. Start x11vnc          : ./scripts/start_vnc.sh"
echo "  3. Validate health       : ./scripts/health_check.sh"
echo "  4. Run automation        : source .venv/bin/activate && python src/main.py"
