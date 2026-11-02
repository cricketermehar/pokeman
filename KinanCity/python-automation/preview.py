"""
preview.py
==========
Interactive Live Automation Dashboard for KinanCity & Playwright.
Zero external dependencies (uses standard Python library).

Starts a local web UI at: http://localhost:8080
Features:
  - Input count and hit Enter / Click to create N accounts as an independent Order
  - Live progress bar and real-time execution log stream
  - Download Excel / CSV for EACH INDIVIDUAL ORDER (iteration-specific download)
  - Direct Download Banner for newly created orders
  - Order Batches & Iterations history table with per-order download buttons
  - Filter accounts table by specific Order or view All
  - Show/Hide password toggle and copy-to-clipboard buttons
  - Live metrics and health indicators
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
from http import server
from pathlib import Path
from typing import Any, Dict, List

PORT = 8080
BASE_DIR = Path(__file__).parent.resolve()
PLAYWRIGHT_DIR = (BASE_DIR.parent / "kinancity-playwright").resolve()
CREATED_ACCOUNTS_FILE = PLAYWRIGHT_DIR / "created_accounts.txt"
ORDERS_DIR = PLAYWRIGHT_DIR / "orders"
ORDERS_DIR.mkdir(parents=True, exist_ok=True)

# Thread-safe global state for batch executions
batch_lock = threading.Lock()
batch_state = {
    "is_running": False,
    "order_id": "",
    "total": 0,
    "completed": 0,
    "current_account": "",
    "status_message": "Ready to create accounts",
    "recent_logs": [],
    "last_error": None,
    "last_completed_order": None,
    "start_time": 0,
}


def load_created_accounts() -> List[Dict[str, str]]:
    """Parse created_accounts.txt and return structured records."""
    records = []
    if not CREATED_ACCOUNTS_FILE.exists():
        return records

    try:
        with open(CREATED_ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                username = parts[0] if len(parts) > 0 else ""
                password = parts[1] if len(parts) > 1 else ""
                email = parts[2] if len(parts) > 2 else ""
                order_id = parts[3] if len(parts) > 3 else "ORD-001"
                records.append({
                    "id": idx,
                    "order_id": order_id,
                    "username": username,
                    "password": password,
                    "email": email,
                    "status": "ACTIVATED",
                    "method": "Sandbox Automation",
                })
    except Exception as e:
        print(f"[Dashboard] Error reading created_accounts.txt: {e}")
    return records


def load_orders() -> List[Dict[str, Any]]:
    """Group accounts by order_id or read from orders metadata."""
    accounts = load_created_accounts()
    orders_map: Dict[str, Dict[str, Any]] = {}

    # 1. Load from saved order JSON files
    if ORDERS_DIR.exists():
        for json_file in sorted(ORDERS_DIR.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    oid = data.get("orderId") or json_file.stem
                    orders_map[oid] = {
                        "order_id": oid,
                        "created_at": data.get("createdAt", ""),
                        "count": data.get("completedCount", len(data.get("accounts", []))),
                        "status": data.get("status", "COMPLETED"),
                        "accounts": data.get("accounts", []),
                    }
            except Exception:
                pass

    # 2. Reconcile with accounts in created_accounts.txt
    for acc in accounts:
        oid = acc.get("order_id", "ORD-001")
        if oid not in orders_map:
            orders_map[oid] = {
                "order_id": oid,
                "created_at": "Saved Iteration",
                "count": 0,
                "status": "COMPLETED",
                "accounts": [],
            }
        if not any(a.get("username") == acc["username"] for a in orders_map[oid]["accounts"]):
            orders_map[oid]["accounts"].append(acc)
            orders_map[oid]["count"] = len(orders_map[oid]["accounts"])

    orders_list = list(orders_map.values())
    orders_list.sort(key=lambda o: o["order_id"], reverse=True)
    return orders_list


def get_next_order_id() -> str:
    """Calculate next sequential order ID (e.g. ORD-004)."""
    orders = load_orders()
    max_num = 0
    for o in orders:
        m = re.match(r"ORD-(\d+)", o["order_id"])
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"ORD-{str(max_num + 1).zfill(3)}"


def run_batch_thread(count: int, order_id: str):
    """Background worker thread that runs the TypeScript Playwright batch creator."""
    global batch_state
    with batch_lock:
        batch_state["is_running"] = True
        batch_state["order_id"] = order_id
        batch_state["total"] = count
        batch_state["completed"] = 0
        batch_state["current_account"] = "Initializing Playwright engine..."
        batch_state["status_message"] = f"Starting Order {order_id} ({count} accounts)..."
        batch_state["last_error"] = None
        batch_state["start_time"] = time.time()
        batch_state["recent_logs"].append(
            f"[{time.strftime('%H:%M:%S')}] 🚀 Order {order_id}: Initiated creation of {count} accounts"
        )

    cmd = ["npx", "ts-node", "src/scripts/createBatchAccounts.ts", str(count), order_id]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(PLAYWRIGHT_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        account_pattern = re.compile(r"Creating Account:\s+([a-zA-Z0-9_]+)")
        success_pattern = re.compile(r"Successfully created and activated")

        if process.stdout:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue

                with batch_lock:
                    batch_state["recent_logs"].append(f"[{time.strftime('%H:%M:%S')}] {line}")
                    if len(batch_state["recent_logs"]) > 100:
                        batch_state["recent_logs"].pop(0)

                    acc_match = account_pattern.search(line)
                    if acc_match:
                        acc_name = acc_match.group(1)
                        batch_state["current_account"] = acc_name
                        batch_state["status_message"] = f"[{order_id}] Registering {acc_name}..."

                    if success_pattern.search(line):
                        batch_state["completed"] += 1
                        batch_state["status_message"] = f"[{order_id}] Created {batch_state['completed']} of {batch_state['total']} accounts"

        process.wait()

        with batch_lock:
            batch_state["is_running"] = False
            batch_state["current_account"] = ""
            if process.returncode == 0:
                batch_state["status_message"] = f"✅ Order {order_id} Completed! All {count} accounts created & activated."
                batch_state["recent_logs"].append(
                    f"[{time.strftime('%H:%M:%S')}] ✅ Order {order_id} finished successfully. Ready to download!"
                )
                batch_state["last_completed_order"] = {
                    "order_id": order_id,
                    "count": batch_state["completed"],
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
            else:
                batch_state["status_message"] = f"Order {order_id} finished with errors."
                batch_state["last_error"] = f"Exited with code {process.returncode}"

    except Exception as e:
        with batch_lock:
            batch_state["is_running"] = False
            batch_state["status_message"] = f"Execution error: {e}"
            batch_state["last_error"] = str(e)
            batch_state["recent_logs"].append(f"[{time.strftime('%H:%M:%S')}] ❌ ERROR: {e}")


class DashboardHandler(server.SimpleHTTPRequestHandler):

    def do_POST(self):
        if self.path == "/api/create-batch":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                payload = json.loads(body)
                count = int(payload.get("count", 5))
                count = max(1, min(count, 100000))
            except Exception:
                count = 5

            with batch_lock:
                if batch_state["is_running"]:
                    self.send_response(409)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "A batch order is currently in progress"}).encode("utf-8"))
                    return

            order_id = get_next_order_id()
            thread = threading.Thread(target=run_batch_thread, args=(count, order_id), daemon=True)
            thread.start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "order_id": order_id, "count": count}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        # 1. API Status Endpoint
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            created_accounts = load_created_accounts()
            orders = load_orders()
            next_order_id = get_next_order_id()

            with batch_lock:
                state_copy = dict(batch_state)
                logs_copy = list(batch_state["recent_logs"])[-35:]

            payload = {
                "batch": state_copy,
                "orders": orders,
                "next_order_id": next_order_id,
                "created_accounts": created_accounts,
                "total_created": len(created_accounts),
                "logs": logs_copy,
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        # 2. Download Excel / CSV Endpoint (Iteration/Order-specific or All)
        elif self.path.startswith("/api/download-excel") or self.path.startswith("/api/download-csv"):
            parsed_url = urllib.parse.urlparse(self.path)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            target_order_id = query_params.get("order_id", [None])[0] or query_params.get("order", [None])[0]

            # If specific order requested and CSV file already created in orders/
            if target_order_id:
                order_csv_path = ORDERS_DIR / f"{target_order_id}.csv"
                if order_csv_path.exists():
                    with open(order_csv_path, "rb") as f:
                        csv_data = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", f'attachment; filename="kinancity_{target_order_id}.csv"')
                    self.send_header("Content-Length", str(len(csv_data)))
                    self.end_headers()
                    self.wfile.write(csv_data)
                    return

            # Otherwise filter from loaded accounts or export all
            all_accounts = load_created_accounts()
            if target_order_id:
                accounts = [a for a in all_accounts if a.get("order_id") == target_order_id]
                filename = f"kinancity_{target_order_id}.csv"
            else:
                accounts = all_accounts
                filename = "kinancity_all_accounts.csv"

            output = io.StringIO()
            output.write("\ufeff")  # UTF-8 BOM for Microsoft Excel compatibility
            writer = csv.writer(output)
            writer.writerow(["#", "Order ID", "Username", "Password", "Email Address", "Account Status", "Creation Engine", "Created Timestamp"])

            for idx, acc in enumerate(accounts, 1):
                writer.writerow([
                    idx,
                    acc.get("order_id", "ORD-001"),
                    acc["username"],
                    acc["password"],
                    acc["email"],
                    acc["status"],
                    acc["method"],
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                ])

            csv_data = output.getvalue().encode("utf-8-sig")

            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(csv_data)))
            self.end_headers()
            self.wfile.write(csv_data)
            return

        # 3. Main Dashboard UI
        elif self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.render_dashboard_html().encode("utf-8"))
            return

        super().do_GET()

    def render_dashboard_html(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KinanCity Automation — Live Order Dashboard & Per-Iteration Excel</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0b0f17;
      --card-bg: rgba(22, 27, 34, 0.78);
      --card-border: rgba(48, 54, 61, 0.8);
      --text: #c9d1d9;
      --heading: #f0f6fc;
      --primary: #58a6ff;
      --primary-hover: #388bfd;
      --primary-glow: rgba(88, 166, 255, 0.25);
      --success: #3fb950;
      --success-glow: rgba(63, 185, 80, 0.25);
      --warning: #d29922;
      --danger: #f85149;
      --purple: #bc8cff;
      --order-gold: #f59e0b;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Outfit', -apple-system, sans-serif;
      background: radial-gradient(circle at 12% 10%, #111827 0%, var(--bg) 100%);
      color: var(--text);
      padding: 2rem;
      min-height: 100vh;
    }
    .container { max-width: 1440px; margin: 0 auto; }
    
    /* Top Header */
    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      padding-bottom: 1.25rem;
      border-bottom: 1px solid var(--card-border);
    }
    .brand { display: flex; align-items: center; gap: 0.85rem; }
    .brand-icon {
      font-size: 1.85rem;
      background: linear-gradient(135deg, #388bfd, #bc8cff);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .brand-title { font-size: 1.75rem; font-weight: 800; color: var(--heading); letter-spacing: -0.02em; }
    .status-badge {
      font-size: 0.75rem;
      padding: 0.35rem 0.75rem;
      border-radius: 999px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }
    .badge-auto { background: rgba(63, 185, 80, 0.15); color: var(--success); border: 1px solid rgba(63, 185, 80, 0.4); }
    .pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); animation: pulse 1.5s infinite; }
    @keyframes pulse { 0% { opacity: 0.4; } 50% { opacity: 1; } 100% { opacity: 0.4; } }

    /* New Order Completion Alert Banner */
    .order-alert-box {
      background: linear-gradient(90deg, rgba(16, 185, 129, 0.15) 0%, rgba(59, 130, 246, 0.15) 100%);
      border: 1px solid rgba(52, 211, 153, 0.5);
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 4px 20px rgba(16, 185, 129, 0.2);
      animation: slideDown 0.4s ease;
    }
    @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
    .alert-content { display: flex; align-items: center; gap: 1rem; }
    .alert-icon { font-size: 2rem; }
    .btn-download-order {
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      color: #fff;
      font-weight: 700;
      padding: 0.65rem 1.25rem;
      border-radius: 8px;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
      transition: all 0.2s ease;
    }
    .btn-download-order:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(16, 185, 129, 0.6); }

    /* Action Control Box */
    .action-card {
      background: linear-gradient(180deg, rgba(30, 41, 59, 0.75) 0%, rgba(22, 27, 34, 0.9) 100%);
      border: 1px solid rgba(88, 166, 255, 0.35);
      border-radius: 12px;
      padding: 1.75rem;
      margin-bottom: 2rem;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4), 0 0 20px var(--primary-glow);
      backdrop-filter: blur(10px);
    }
    .action-title { font-size: 1.25rem; font-weight: 700; color: var(--heading); margin-bottom: 0.3rem; display: flex; align-items: center; gap: 0.6rem; }
    .action-desc { font-size: 0.9rem; color: #8b949e; margin-bottom: 1.25rem; }
    .action-form { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; }
    .input-group { display: flex; align-items: center; gap: 0.75rem; }
    .input-label { font-size: 0.9rem; font-weight: 600; color: var(--heading); }
    .number-input {
      background: #090d13;
      border: 1px solid #484f58;
      color: #fff;
      padding: 0.75rem 1rem;
      border-radius: 8px;
      font-size: 1.1rem;
      font-weight: 600;
      width: 140px;
      outline: none;
      transition: all 0.2s ease;
      font-family: 'JetBrains Mono', monospace;
    }
    .number-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
    
    .btn {
      padding: 0.75rem 1.4rem;
      border-radius: 8px;
      font-size: 0.95rem;
      font-weight: 700;
      cursor: pointer;
      border: none;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      text-decoration: none;
    }
    .btn-primary {
      background: linear-gradient(135deg, #1f6feb 0%, #238636 100%);
      color: #fff;
      box-shadow: 0 4px 15px rgba(35, 134, 54, 0.35);
    }
    .btn-primary:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(35, 134, 54, 0.5);
    }
    .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }
    
    .btn-all-excel {
      background: rgba(255, 255, 255, 0.05);
      color: #c9d1d9;
      border: 1px solid var(--card-border);
      margin-left: auto;
    }
    .btn-all-excel:hover { background: rgba(255, 255, 255, 0.1); color: #fff; transform: translateY(-2px); }

    /* Progress bar */
    .progress-wrap { margin-top: 1.25rem; display: none; }
    .progress-bar-bg { background: #161b22; border-radius: 999px; height: 10px; overflow: hidden; border: 1px solid var(--card-border); }
    .progress-bar-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #1f6feb, #3fb950); transition: width 0.3s ease; }
    .progress-info { display: flex; justify-content: space-between; font-size: 0.85rem; margin-top: 0.4rem; color: #8b949e; }

    /* Metrics Cards */
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .metric-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 10px;
      padding: 1.25rem;
      backdrop-filter: blur(8px);
    }
    .metric-num { font-size: 2.2rem; font-weight: 800; color: var(--heading); font-family: 'JetBrains Mono', monospace; }
    .metric-label { font-size: 0.8rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-top: 0.3rem; }

    /* Orders Card */
    .orders-panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 2rem;
      backdrop-filter: blur(8px);
    }

    /* Grid Layout */
    .grid { display: grid; grid-template-columns: 3fr 2fr; gap: 1.5rem; }
    @media (max-width: 1024px) { .grid { grid-template-columns: 1fr; } }

    .panel {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 1.5rem;
      backdrop-filter: blur(8px);
    }
    .panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.75rem; }
    .panel-title { font-size: 1.15rem; font-weight: 700; color: var(--heading); display: flex; align-items: center; gap: 0.5rem; }

    /* Table styling */
    .table-container { overflow-x: auto; max-height: 480px; overflow-y: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { text-align: left; padding: 0.85rem 1rem; border-bottom: 1px solid var(--card-border); }
    th { color: #8b949e; font-size: 0.75rem; text-transform: uppercase; font-weight: 700; position: sticky; top: 0; background: #161b22; z-index: 1; }
    tbody tr:hover { background: rgba(255, 255, 255, 0.03); }

    .order-badge {
      font-family: 'JetBrains Mono', monospace;
      font-weight: 700;
      font-size: 0.8rem;
      padding: 0.25rem 0.55rem;
      border-radius: 6px;
      background: rgba(245, 158, 11, 0.15);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
      display: inline-block;
    }
    .acc-user { font-family: 'JetBrains Mono', monospace; font-weight: 600; color: #58a6ff; display: inline-flex; align-items: center; gap: 0.4rem; }
    .acc-pass { font-family: 'JetBrains Mono', monospace; color: #8b949e; font-size: 0.85rem; }
    .pass-masked { letter-spacing: 0.15em; }
    .copy-btn { background: none; border: none; cursor: pointer; color: #8b949e; font-size: 0.85rem; padding: 2px 4px; border-radius: 4px; }
    .copy-btn:hover { color: #fff; background: rgba(255, 255, 255, 0.1); }

    .badge-activated { background: rgba(63, 185, 80, 0.15); color: #3fb950; border: 1px solid rgba(63, 185, 80, 0.3); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }

    .btn-download-sm {
      background: rgba(35, 134, 54, 0.2);
      color: #7ee787;
      border: 1px solid rgba(63, 185, 80, 0.45);
      padding: 0.35rem 0.75rem;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: 6px;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      transition: all 0.2s ease;
    }
    .btn-download-sm:hover {
      background: rgba(35, 134, 54, 0.35);
      color: #fff;
      transform: translateY(-1px);
    }

    .filter-select {
      background: #090d13;
      border: 1px solid #484f58;
      color: #fff;
      padding: 0.35rem 0.75rem;
      border-radius: 6px;
      font-size: 0.85rem;
      outline: none;
    }

    /* Live terminal logs */
    .logs-box {
      background: #06090e;
      border: 1px solid #21262d;
      border-radius: 8px;
      padding: 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: #7ee787;
      height: 480px;
      overflow-y: auto;
      line-height: 1.5;
    }
    .log-line { margin-bottom: 0.3rem; white-space: pre-wrap; word-break: break-all; }
  </style>
</head>
<body>
  <div class="container">
    
    <!-- Top Header -->
    <div class="header">
      <div class="brand">
        <span class="brand-icon">⚡</span>
        <div>
          <div class="brand-title">KinanCity Automation Dashboard</div>
          <div style="font-size: 0.85rem; color: #8b949e;">Order-Based Account Batch Creator & Per-Iteration Excel Exporter</div>
        </div>
      </div>
      <div class="status-badge badge-auto">
        <span class="pulse-dot"></span>
        <span>Sandbox Auto-Solver Active (0 Clicks)</span>
      </div>
    </div>

    <!-- Dynamic Alert: Newly Completed Order Banner -->
    <div id="new-order-banner" class="order-alert-box" style="display: none;">
      <div class="alert-content">
        <span class="alert-icon">🎉</span>
        <div>
          <strong id="banner-order-title" style="color: #fff; font-size: 1.1rem;">New Order Ready!</strong>
          <div id="banner-order-desc" style="font-size: 0.88rem; color: #a7f3d0; margin-top: 0.2rem;">All accounts created and verified for this iteration.</div>
        </div>
      </div>
      <a href="#" id="banner-download-btn" class="btn-download-order">
        <span>📥</span>
        <span id="banner-download-text">Download This Order (.csv)</span>
      </a>
    </div>

    <!-- Interactive Creation Controller -->
    <div class="action-card">
      <div class="action-title">
        <span>Create New Account Order</span>
        <span class="order-badge" id="badge-next-order">Next: ORD-004</span>
      </div>
      <div class="action-desc">Enter the count for this iteration and press Enter. Each batch creates an isolated order that you can download independently.</div>
      
      <form class="action-form" id="batch-form" onsubmit="event.preventDefault(); startBatch();">
        <div class="input-group">
          <label class="input-label" for="count-input">Number of Accounts:</label>
          <input type="number" id="count-input" class="number-input" value="5" min="1" max="100000" required autofocus>
        </div>

        <button type="submit" id="start-btn" class="btn btn-primary">
          <span>🚀</span>
          <span id="start-btn-text">Submit Order (Enter)</span>
        </button>

        <a href="/api/download-excel?all=true" class="btn btn-all-excel" id="download-all-btn" title="Download cumulative accounts across all past orders">
          <span>📦</span>
          <span>Download All Past History (.csv)</span>
        </a>
      </form>

      <!-- Animated Progress Bar -->
      <div class="progress-wrap" id="progress-container">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" id="progress-bar"></div>
        </div>
        <div class="progress-info">
          <span id="progress-status">Initializing engine...</span>
          <span id="progress-percent">0%</span>
        </div>
      </div>
    </div>

    <!-- Live Metrics Overview -->
    <div class="metrics">
      <div class="metric-card">
        <div class="metric-num" id="metric-total-created" style="color: var(--success);">0</div>
        <div class="metric-label">Total Accounts Activated</div>
      </div>
      <div class="metric-card">
        <div class="metric-num" id="metric-total-orders" style="color: #fbbf24;">0</div>
        <div class="metric-label">Completed Orders / Batches</div>
      </div>
      <div class="metric-card">
        <div class="metric-num" id="metric-current-batch" style="color: var(--primary);">Idle</div>
        <div class="metric-label">Engine Status</div>
      </div>
      <div class="metric-card">
        <div class="metric-num" id="metric-captcha-clicks" style="color: #79c0ff;">0</div>
        <div class="metric-label">Manual Clicks Required</div>
      </div>
    </div>

    <!-- Section 1: Order Batches & Iterations (Each with its own download button!) -->
    <div class="orders-panel">
      <div class="panel-header">
        <div class="panel-title">
          <span>📦</span>
          <span>Order Batches & Iterations</span>
          <span style="font-size: 0.8rem; font-weight: 500; color: #8b949e;" id="orders-count-label">(0 Orders)</span>
        </div>
        <span style="font-size: 0.8rem; color: #8b949e;">Each order downloads ONLY that particular iteration's accounts</span>
      </div>

      <div class="table-container" style="max-height: 280px;">
        <table>
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Created Timestamp</th>
              <th>Accounts Count</th>
              <th>Batch Status</th>
              <th>Download Specific Iteration</th>
            </tr>
          </thead>
          <tbody id="orders-tbody">
            <tr><td colspan="5" style="text-align: center; color: #8b949e; padding: 1.5rem;">Loading orders...</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Section 2: Main Content Grid (Accounts Table & Live Log Stream) -->
    <div class="grid">
      
      <!-- Panel 1: Created Accounts Table -->
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <span>📋</span>
            <span>Created Accounts</span>
            <span style="font-size: 0.8rem; font-weight: 500; color: #8b949e;" id="table-count-label">(0)</span>
          </div>
          
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <select id="order-filter-select" class="filter-select" onchange="filterAccountsByOrder()">
              <option value="ALL">All Orders</option>
            </select>

            <button onclick="togglePasswords()" class="btn" style="padding: 0.35rem 0.75rem; font-size: 0.8rem; background: rgba(255,255,255,0.08); color: #c9d1d9;">
              <span id="pass-toggle-icon">👁️</span> <span id="pass-toggle-text">Show Passwords</span>
            </button>
          </div>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Order</th>
                <th>Username</th>
                <th>Password</th>
                <th>Email</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody id="accounts-tbody">
              <tr><td colspan="6" style="text-align: center; color: #8b949e; padding: 2rem;">Loading accounts...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Panel 2: Live Engine Stream -->
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">
            <span>⚡</span>
            <span>Live Playwright Stream</span>
          </div>
          <span style="font-size: 0.75rem; color: #8b949e;">Auto-scrolling</span>
        </div>
        <div class="logs-box" id="logs-terminal">Waiting for creation task...</div>
      </div>

    </div>
  </div>

  <script>
    let showPasswords = false;
    let cachedAccounts = [];
    let cachedOrders = [];
    let selectedOrderFilter = 'ALL';
    let lastNotifiedOrderId = null;

    function togglePasswords() {
      showPasswords = !showPasswords;
      document.getElementById('pass-toggle-text').innerText = showPasswords ? 'Hide Passwords' : 'Show Passwords';
      document.getElementById('pass-toggle-icon').innerText = showPasswords ? '🔒' : '👁️';
      renderAccountsTable();
    }

    function filterAccountsByOrder() {
      const select = document.getElementById('order-filter-select');
      selectedOrderFilter = select.value;
      renderAccountsTable();
    }

    async function startBatch() {
      const input = document.getElementById('count-input');
      const count = parseInt(input.value, 10);
      if (isNaN(count) || count <= 0) {
        alert('Please enter a valid number of accounts (e.g. 5)');
        return;
      }

      const btn = document.getElementById('start-btn');
      btn.disabled = true;
      document.getElementById('start-btn-text').innerText = 'Starting order...';

      try {
        const res = await fetch('/api/create-batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ count: count })
        });

        if (!res.ok) {
          const err = await res.json();
          alert(err.error || 'Failed to start order');
          btn.disabled = false;
          document.getElementById('start-btn-text').innerText = 'Submit Order (Enter)';
        } else {
          // Hide previous completion banner when a new order starts
          document.getElementById('new-order-banner').style.display = 'none';
        }
      } catch (e) {
        alert('Error connecting to dashboard server');
        btn.disabled = false;
        document.getElementById('start-btn-text').innerText = 'Submit Order (Enter)';
      }
    }

    function renderOrdersTable(orders) {
      cachedOrders = orders || [];
      const tbody = document.getElementById('orders-tbody');
      document.getElementById('orders-count-label').innerText = `(${cachedOrders.length} Orders)`;
      document.getElementById('metric-total-orders').innerText = cachedOrders.length;

      // Populate filter select options if changed
      const select = document.getElementById('order-filter-select');
      const currentVal = select.value;
      let optionsHtml = '<option value="ALL">All Orders</option>';
      for (const ord of cachedOrders) {
        optionsHtml += `<option value="${ord.order_id}">${ord.order_id} (${ord.count} accounts)</option>`;
      }
      select.innerHTML = optionsHtml;
      select.value = currentVal;

      if (cachedOrders.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: #8b949e; padding: 1.5rem;">No orders created yet.</td></tr>';
        return;
      }

      tbody.innerHTML = cachedOrders.map(ord => {
        const timestamp = ord.created_at || 'Just now';
        return `
          <tr>
            <td><span class="order-badge">${ord.order_id}</span></td>
            <td style="color: #8b949e; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;">${timestamp}</td>
            <td style="font-weight: 600; color: #f0f6fc;">${ord.count} accounts</td>
            <td><span class="badge-activated">✅ ${ord.status || 'COMPLETED'}</span></td>
            <td>
              <a href="/api/download-excel?order_id=${ord.order_id}" class="btn-download-sm">
                <span>📥</span>
                <span>Download ${ord.order_id} Excel (.csv)</span>
              </a>
            </td>
          </tr>
        `;
      }).join('');
    }

    function renderAccountsTable() {
      const tbody = document.getElementById('accounts-tbody');
      let accounts = cachedAccounts;

      if (selectedOrderFilter !== 'ALL') {
        accounts = accounts.filter(a => a.order_id === selectedOrderFilter);
      }

      document.getElementById('table-count-label').innerText = `(${accounts.length} of ${cachedAccounts.length})`;

      if (accounts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #8b949e; padding: 2rem;">No accounts found for selected filter.</td></tr>';
        return;
      }

      const reversed = [...accounts].reverse();
      tbody.innerHTML = reversed.map((acc, i) => {
        const idx = accounts.length - i;
        const passDisplay = showPasswords ? acc.password : '••••••••••••';
        const ordId = acc.order_id || 'ORD-001';
        return `
          <tr>
            <td style="color: #8b949e; font-weight: 600;">${idx}</td>
            <td><span class="order-badge" style="font-size: 0.72rem; padding: 0.15rem 0.4rem;">${ordId}</span></td>
            <td>
              <span class="acc-user">${acc.username}</span>
              <button class="copy-btn" onclick="copyText('${acc.username}')" title="Copy username">📋</button>
            </td>
            <td>
              <span class="acc-pass ${showPasswords ? '' : 'pass-masked'}">${passDisplay}</span>
              <button class="copy-btn" onclick="copyText('${acc.password}')" title="Copy password">📋</button>
            </td>
            <td style="color: #8b949e; font-size: 0.85rem;">${acc.email}</td>
            <td><span class="badge-activated">✅ Activated</span></td>
          </tr>
        `;
      }).join('');
    }

    function copyText(str) {
      navigator.clipboard.writeText(str);
    }

    async function updateDashboard() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();

        // 1. Update Metrics
        document.getElementById('metric-total-created').innerText = data.total_created || 0;
        if (data.next_order_id) {
          document.getElementById('badge-next-order').innerText = `Next: ${data.next_order_id}`;
        }

        // 2. Update Batch Execution State & Progress
        const batch = data.batch || {};
        const btn = document.getElementById('start-btn');
        const progressWrap = document.getElementById('progress-container');

        if (batch.is_running) {
          btn.disabled = true;
          document.getElementById('start-btn-text').innerText = `Creating ${batch.order_id} (${batch.completed}/${batch.total})...`;
          document.getElementById('metric-current-batch').innerText = `Running (${batch.order_id})`;
          document.getElementById('metric-current-batch').style.color = '#58a6ff';

          progressWrap.style.display = 'block';
          const pct = Math.round((batch.completed / (batch.total || 1)) * 100);
          document.getElementById('progress-bar').style.width = pct + '%';
          document.getElementById('progress-percent').innerText = pct + '%';
          document.getElementById('progress-status').innerText = batch.status_message || 'Processing accounts...';
        } else {
          btn.disabled = false;
          document.getElementById('start-btn-text').innerText = 'Submit Order (Enter)';
          document.getElementById('metric-current-batch').innerText = 'Idle';
          document.getElementById('metric-current-batch').style.color = '#3fb950';

          if (batch.completed > 0 && batch.completed === batch.total) {
            document.getElementById('progress-status').innerText = `✅ Order ${batch.order_id} Complete! Created ${batch.total} accounts.`;
            document.getElementById('progress-bar').style.width = '100%';
            document.getElementById('progress-percent').innerText = '100%';
            setTimeout(() => {
              if (!batch.is_running) progressWrap.style.display = 'none';
            }, 4000);
          } else {
            progressWrap.style.display = 'none';
          }
        }

        // 3. New Order Ready Notification Banner
        if (batch.last_completed_order && batch.last_completed_order.order_id !== lastNotifiedOrderId) {
          lastNotifiedOrderId = batch.last_completed_order.order_id;
          const banner = document.getElementById('new-order-banner');
          const title = document.getElementById('banner-order-title');
          const desc = document.getElementById('banner-order-desc');
          const downloadBtn = document.getElementById('banner-download-btn');
          const downloadText = document.getElementById('banner-download-text');

          title.innerText = `🎉 Order ${batch.last_completed_order.order_id} Created Successfully!`;
          desc.innerText = `${batch.last_completed_order.count} accounts activated. Download this specific iteration below:`;
          downloadBtn.href = `/api/download-excel?order_id=${batch.last_completed_order.order_id}`;
          downloadText.innerText = `Download Order ${batch.last_completed_order.order_id} Excel (.csv)`;
          banner.style.display = 'flex';
        }

        // 4. Render Orders & Accounts
        renderOrdersTable(data.orders || []);
        cachedAccounts = data.created_accounts || [];
        renderAccountsTable();

        // 5. Render Logs
        const terminal = document.getElementById('logs-terminal');
        if (data.logs && data.logs.length > 0) {
          terminal.innerHTML = data.logs.map(l => `<div class="log-line">${l}</div>`).join('');
          terminal.scrollTop = terminal.scrollHeight;
        }

      } catch (err) {
        console.error('Update failed:', err);
      }
    }

    // Refresh every 1.5 seconds for snappy real-time responsiveness
    updateDashboard();
    setInterval(updateDashboard, 1500);
  </script>
</body>
</html>
"""


def run_server():
    os.chdir(BASE_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        print("==================================================")
        print("  ⚡ KinanCity Interactive Batch Dashboard")
        print(f"  URL: http://localhost:{PORT}")
        print("  Features: Iteration-based Order Management")
        print("  Download: /api/download-excel?order_id=<id>")
        print("==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dashboard server.")


if __name__ == "__main__":
    run_server()
