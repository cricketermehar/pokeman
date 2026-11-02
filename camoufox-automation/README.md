# Camoufox + Playwright + Xvfb + x11vnc Browser Automation Framework

Production-grade headed browser automation framework for Linux (Ubuntu 22.04 / 24.04 LTS), featuring a virtual X11 display, secure SSH-tunneled x11vnc remote desktop, Human-in-the-Loop (HITL) interactive login, and secure session state persistence.

---

## 1. Verified Technology Stack & Dependency Matrix

| Technology | Verified Version | Role | Compatibility Verification |
| :--- | :--- | :--- | :--- |
| **Camoufox** | `0.5.6` | Anti-detect Firefox wrapper | Verified on PyPI; requires `playwright<1.63` |
| **Playwright** | `1.62.0` | Browser automation engine | Satisfies `playwright<1.63` requirement |
| **Xvfb** | Standard OS package | Headed virtual X11 display | Dynamic display allocation, conflict prevention |
| **x11vnc** | Standard OS package | Secure remote desktop | Bound strictly to `127.0.0.1` (localhost only) |
| **SSH Tunneling** | OpenSSH | Encrypted local port forward | End-to-end encrypted remote desktop control |
| **Python** | 3.10, 3.11, 3.12, 3.14 | Runtime environment | Type-annotated, Pydantic-validated |

---

## 2. Architecture & Interactive Login Workflow

```text
Python Automation Runner (main.py / workflow.py)
                   │
                   ▼
       Xvfb Virtual X11 Display (:99 / dynamic)
                   │
                   ▼
         Camoufox Headed Firefox
                   │
                   ▼
     Playwright Browser Context Control
                   │
                   ▼
         Authorized Target Portal
                   │
        Is Authentication Required?
              /           \
            Yes            No
             │              │
             ▼              │
    x11vnc (127.0.0.1:5900)  │
             │              │
             ▼              │
  Encrypted SSH Tunnel      │
   (localhost:5900)         │
             │              │
             ▼              │
  Human Operator Login      │
   (Credentials/MFA/OTP)    │
             │              │
             ▼              │
  Validate Success Indicator │
   (Dashboard/Profile/Logout)│
             │              │
             ▼              │
  Save Storage State (0600) │
             │              │
             └───────┬──────┘
                     │
                     ▼
        Authorized Automated Tasks
                     │
                     ▼
       Diagnostic Screenshots & Logs
```

---

## 3. Project Directory Structure

```text
camoufox-automation/
├── README.md               # Architecture, setup, and operations guide
├── requirements.txt        # Verified dependencies (camoufox==0.5.6, playwright==1.62.0)
├── .env.example            # Environment configuration template
├── .gitignore              # Protects sessions, logs, screenshots, and credentials
├── pytest.ini              # Test runner configuration
├── scripts/
│   ├── install.sh          # Installs Linux OS packages, Python virtualenv, and browser
│   ├── start_display.sh    # Starts Xvfb with dynamic port conflict resolution
│   ├── start_vnc.sh        # Starts x11vnc securely bound to localhost
│   ├── stop_services.sh    # Gracefully stops all virtual display and VNC services
│   └── health_check.sh     # Comprehensive diagnostics and readiness verifier
├── src/
│   ├── __init__.py
│   ├── main.py             # CLI entrypoint with --check, --headless, --clear-session
│   ├── browser_manager.py  # Camoufox lifecycle, context creation, screenshots, teardown
│   ├── session_manager.py  # 0600 storage state persistence & cookie expiration checks
│   ├── authentication.py   # State evaluation & Human-in-the-Loop VNC pause handler
│   ├── workflow.py         # End-to-end execution orchestrator
│   ├── config.py           # Pydantic Settings environment configuration
│   └── logger.py           # Structured logging with sensitive data redaction
├── tests/
│   ├── conftest.py         # Pytest environment bootstrap
│   ├── test_browser.py     # Display environment and browser teardown unit tests
│   ├── test_session.py     # Storage state, expiration, and sanitization tests
│   └── test_workflow.py    # Authentication state and timeout handling tests
├── sessions/               # Authenticated storage state JSON files (chmod 0700)
├── screenshots/            # Timestamped diagnostic screenshots
└── logs/                   # Process logs, PID tracking, and automation logs
```

---

## 4. Setup & Installation on Ubuntu Linux

### Step 1: Run System Installation Script
```bash
cd camoufox-automation
chmod +x scripts/*.sh
./scripts/install.sh
```
The script will:
1. Install OS packages: `xvfb`, `x11vnc`, `fluxbox`, `xterm`, `openssh-server`, and graphics libraries.
2. Create a virtual environment `.venv`.
3. Install pinned dependencies (`camoufox==0.5.6`, `playwright==1.62.0`).
4. Download the Camoufox browser assets (`python3 -m camoufox fetch`).
5. Configure `~/.vnc/passwd` with `0600` permissions.

### Step 2: Configure Environment
Copy and customize `.env`:
```bash
cp .env.example .env
nano .env
```
Key configuration parameters:
* `TARGET_URL`: Portal URL to automate (e.g. `https://example.com/dashboard`).
* `AUTH_SUCCESS_SELECTOR`: CSS selector present only when logged in (e.g. `#dashboard, a[href*="logout"]`).
* `OPERATOR_TIMEOUT_SEC`: Timeout in seconds allowed for manual operator login (default: `300`).
* `VNC_PORT`: Port for internal VNC listener (default: `5900`).

---

## 5. Starting the Virtual Display & Secure VNC

### 1. Launch Xvfb Virtual Display
```bash
./scripts/start_display.sh
```
* Automatically detects occupied displays and allocates the first available display number.
* Sets up a virtual framebuffer at 1920x1080 with 24-bit color.

### 2. Launch Secure x11vnc Server
```bash
./scripts/start_vnc.sh
```
* Binds strictly to `127.0.0.1` (`-localhost` flag). **It is impossible to connect directly over the WAN.**
* Enforces encrypted password authentication.

### 3. Verify Health
```bash
./scripts/health_check.sh
```

---

## 6. Secure Remote Desktop Connection (SSH Tunneling)

Because `x11vnc` is bound to `127.0.0.1`, you connect through an encrypted SSH local port forward.

### Establish the SSH Tunnel:
Run this command from your **local workstation terminal**:
```bash
ssh -N -L 5900:127.0.0.1:5900 user@YOUR_SERVER_IP
```

### Connect with a VNC Client:
1. Open your VNC viewer (TigerVNC, RealVNC, TightVNC, or macOS Screen Sharing):
   ```text
   vnc://localhost:5900
   ```
2. Enter the VNC password configured during setup.
3. You will see the virtual desktop with Camoufox running.

### Close the SSH Tunnel:
Press `Ctrl + C` in the local SSH terminal when done.

---

## 7. Running the Automation

Activate the virtual environment and run:

```bash
source .venv/bin/activate

# Standard run (headed in virtual X11 display)
python src/main.py

# Custom target URL
python src/main.py --url "https://authorized-portal.com/login"

# Run in headless mode (no VNC needed)
python src/main.py --headless

# Clear stored session and force re-login
python src/main.py --clear-session

# Check environment readiness
python src/main.py --check
```

---

## 8. Interactive Login Flow in Action

When automation encounters an unauthorized session:
1. **Pause**: The automation logger outputs:
   ```text
   [WARNING] 🔒 MANUAL OPERATOR LOGIN REQUIRED (Human-in-the-Loop)
   The application requires authentication at: https://target.com/login
   ```
2. **Operator Action**: Connect via SSH tunnel & VNC, fill credentials, complete MFA/2FA, and click Log In.
3. **Detection**: The engine polls the page and detects the `AUTH_SUCCESS_SELECTOR` (e.g. `#dashboard`).
4. **Session Save**: The engine extracts cookies and localStorage, validating them and saving them to `sessions/authorized_session.json` (`0600` permissions).
5. **Resume**: Automation automatically resumes its authorized tasks.
6. **Subsequent Runs**: Future executions reuse `authorized_session.json` without requiring operator interaction until cookies expire.

---

## 9. Running Automated Tests

Run the test suite:
```bash
source .venv/bin/activate
pytest tests -v
```

Test coverage includes:
* `test_session.py`: Validates session save/load, expiration rejection, JSON corruption handling, and path traversal protection.
* `test_browser.py`: Validates display environment variable configuration, dynamic overrides, and graceful teardown.
* `test_workflow.py`: Validates authentication state detection, operator timeout handling, and execution reporting.

---

## 10. Stopping Services

To cleanly terminate Xvfb, x11vnc, and remove temporary X11 lock files:
```bash
./scripts/stop_services.sh
```

---

## 11. Troubleshooting Guide

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| `Cannot open display :99` | Xvfb not running or crashed | Check `logs/xvfb.log` and verify with `./scripts/start_display.sh` |
| `VNC connection refused on port 5900` | SSH tunnel not running | Verify `ssh -N -L 5900:127.0.0.1:5900` is active on your local machine |
| `Session expired immediately` | Target server sets short-lived cookies | Re-run with `--clear-session` to capture a fresh session token |
| `Camoufox browser binary missing` | Assets not downloaded | Run `python3 -m camoufox fetch` inside `.venv` |
| `Operator verification timed out` | Operator did not log in within timeout | Increase `OPERATOR_TIMEOUT_SEC` in `.env` |
