"""
preview.py
==========
Lightweight local web preview server for KinanCity automation.
Zero external dependencies (uses standard Python library).

Starts a local web UI at: http://localhost:8080
Displays real-time queue states, stats, and run logs.
"""

import http.server
import json
import os
import socketserver
import sys
from pathlib import Path

PORT = 8080
BASE_DIR = Path(__file__).parent


class PreviewHandler(http.server.SimpleHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            state_file = BASE_DIR / "queue_state.json"
            data = {}
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        data = json.load(f)
                except Exception:
                    data = {}

            # Also check latest log file
            log_dir = BASE_DIR / "logs"
            recent_logs = []
            if log_dir.exists():
                log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
                if log_files:
                    try:
                        with open(log_files[0], "r") as f:
                            recent_logs = f.readlines()[-25:]
                    except Exception:
                        pass

            if isinstance(data, list):
                accounts_list = data
            elif isinstance(data, dict):
                accounts_list = list(data.get("accounts", {}).values()) if isinstance(data.get("accounts"), dict) else data.get("accounts", [])
            else:
                accounts_list = []

            payload = {
                "accounts": accounts_list,
                "logs": [l.strip() for l in recent_logs if l.strip()],
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        elif self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.render_html().encode("utf-8"))
            return

        super().do_GET()

    def render_html(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KinanCity Automation — Live Preview</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --heading: #f0f6fc;
      --primary: #58a6ff;
      --success: #3fb950;
      --warning: #d29922;
      --danger: #f85149;
      --purple: #bc8cff;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Outfit', -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 2rem;
      min-height: 100vh;
    }
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1rem;
      border-bottom: 1px solid var(--border);
    }
    .title { font-size: 1.75rem; font-weight: 700; color: var(--heading); display: flex; align-items: center; gap: 0.75rem; }
    .badge {
      font-size: 0.75rem;
      padding: 0.25rem 0.6rem;
      border-radius: 999px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .badge-live { background: rgba(63, 185, 80, 0.2); color: var(--success); border: 1px solid var(--success); }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .metric-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }
    .metric-num { font-size: 2rem; font-weight: 700; color: var(--heading); }
    .metric-label { font-size: 0.85rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }

    .grid { display: grid; grid-template-columns: 3fr 2fr; gap: 1.5rem; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }

    .panel {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
    }
    .panel-title { font-size: 1.1rem; font-weight: 600; color: var(--heading); margin-bottom: 1rem; }

    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid var(--border); }
    th { color: #8b949e; font-size: 0.75rem; text-transform: uppercase; }

    .state-tag {
      display: inline-block;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      font-weight: 600;
    }
    .state-COMPLETED { background: rgba(63, 185, 80, 0.2); color: var(--success); }
    .state-QUEUED { background: rgba(88, 166, 255, 0.2); color: var(--primary); }
    .state-ACTIVE, .state-PGTOOLS_READY, .state-POWERUP { background: rgba(188, 140, 255, 0.2); color: var(--purple); }
    .state-MANUAL_REQUIRED, .state-FAILED_LOGIN { background: rgba(248, 81, 73, 0.2); color: var(--danger); }

    .logs-box {
      background: #090d13;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      color: #7ee787;
      height: 380px;
      overflow-y: auto;
      line-height: 1.4;
    }
    .log-line { margin-bottom: 0.25rem; white-space: pre-wrap; word-break: break-all; }
  </style>
</head>
<body>
  <div class="header">
    <div class="title">
      <span>⚡ KinanCity & PGTools</span>
      <span class="badge badge-live">Live Preview</span>
    </div>
    <div style="font-size: 0.85rem; color: #8b949e;">Auto-refreshing every 2s</div>
  </div>

  <div class="metrics">
    <div class="metric-card">
      <div class="metric-num" id="total-count">0</div>
      <div class="metric-label">Total Accounts</div>
    </div>
    <div class="metric-card">
      <div class="metric-num" style="color: var(--success);" id="completed-count">0</div>
      <div class="metric-label">Completed</div>
    </div>
    <div class="metric-card">
      <div class="metric-num" style="color: var(--primary);" id="pending-count">0</div>
      <div class="metric-label">Pending / Processing</div>
    </div>
    <div class="metric-card">
      <div class="metric-num" style="color: var(--warning);" id="attention-count">0</div>
      <div class="metric-label">Needs Attention</div>
    </div>
  </div>

  <div class="grid">
    <div class="panel">
      <div class="panel-title">Account Queue Status</div>
      <table>
        <thead>
          <tr>
            <th>Username</th>
            <th>State</th>
            <th>Retries</th>
            <th>Last Error / Notes</th>
          </tr>
        </thead>
        <tbody id="account-rows">
          <tr><td colspan="4" style="text-align: center; color: #8b949e;">Loading queue...</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <div class="panel-title">Live Engine Log Stream</div>
      <div class="logs-box" id="log-container">Loading logs...</div>
    </div>
  </div>

  <script>
    async function update() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const accounts = Array.isArray(data.accounts) ? data.accounts : Object.values(data.accounts || {});

        let completed = 0, pending = 0, attention = 0;
        const tbody = document.getElementById('account-rows');
        tbody.innerHTML = '';

        if (accounts.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #8b949e;">No accounts loaded yet.</td></tr>';
        } else {
          accounts.forEach(acc => {
            if (acc.state === 'COMPLETED') completed++;
            else if (['MANUAL_REQUIRED', 'FAILED_LOGIN', 'ACTIVATION_TIMEOUT'].includes(acc.state)) attention++;
            else pending++;

            const tr = document.createElement('tr');
            tr.innerHTML = `
              <td style="font-weight: 600; color: #f0f6fc;">${acc.username}</td>
              <td><span class="state-tag state-${acc.state}">${acc.state}</span></td>
              <td>${acc.retries || 0}</td>
              <td style="color: #8b949e; font-size: 0.8rem;">${acc.last_error || acc.notes || '—'}</td>
            `;
            tbody.appendChild(tr);
          });
        }

        document.getElementById('total-count').innerText = accounts.length;
        document.getElementById('completed-count').innerText = completed;
        document.getElementById('pending-count').innerText = pending;
        document.getElementById('attention-count').innerText = attention;

        const logBox = document.getElementById('log-container');
        if (data.logs && data.logs.length > 0) {
          logBox.innerHTML = data.logs.map(l => `<div class="log-line">${l}</div>`).join('');
          logBox.scrollTop = logBox.scrollHeight;
        } else {
          logBox.innerHTML = '<div style="color: #8b949e;">No log output available yet.</div>';
        }
      } catch (err) {
        console.error(err);
      }
    }

    update();
    setInterval(update, 2000);
  </script>
</body>
</html>
"""


def run_server():
    os.chdir(BASE_DIR)
    with socketserver.TCPServer(("", PORT), PreviewHandler) as httpd:
        print(f"==================================================")
        print(f"  ⚡ KinanCity Live Preview Server")
        print(f"  URL: http://localhost:{PORT}")
        print(f"==================================================")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down preview server.")


if __name__ == "__main__":
    run_server()
