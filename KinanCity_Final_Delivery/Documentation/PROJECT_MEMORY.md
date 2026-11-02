# KinanCity Project Memory & Context Guide

> **Document:** `PROJECT_MEMORY.md`  
> **Repository:** `KinanCity`  
> **Active Branch:** `modernization/build-restore`  
> **Environment:** macOS / Java 17 (Temurin/OpenJDK 17.0.x) / Python 3.9+ / Maven 3.9+  
> **Client Context:** Jason (`jasonhere1`) — KinanCity Modernization & PGTools/UGPhone Automation  

---

## 1. Project Background & Scope

The KinanCity project is a legacy Java-based Pokémon Trainer Club (PTC) account creator and email verification tool. Over time, build dependencies broke, modern Java versions failed to compile it, and Pokémon's authentication infrastructure evolved.

### Deliverables Scope ($150 Phase 1):
1. **KinanCity Java Build Restored:**
   - Java 17 compatibility.
   - Clean Maven build (`mvn clean test` and `mvn clean package` passing across all 14 modules).
   - Removed duplicate / conflicting OkHttp dependencies (pinned to OkHttp 3.14.9).
   - Security redaction: stopped printing plaintext passwords in console logs, proxy URLs, and session logs.
2. **KinanCity-mail Module Restored:**
   - Fixed SubEthaSMTP MIME body parsing (handling single-part text and multipart emails).
   - Fixed activation link regex for modern PTC URLs.
   - Preserved log-mode output for headless link parsing.
3. **Python Automation Backend (`python-automation/`):**
   - Editable, order-preserving, and resumable account queue (`accounts.txt` + `queue_state.json`).
   - Finite State Machine (`state_machine.py`) modeling full account lifecycle.
   - Zero-secret exposure credential store (`credential_store.py`).
   - Exponential backoff retry handler (`retry_handler.py`).
   - Read-only live PTC flow investigator (`ptc_investigator.py`).
   - KinanCity-mail bridge (`mail_watcher.py`).
   - UGPhone cloud-mobile adapter stub for Phase 2 (`adapters/ugphone_adapter.py`).
4. **Out of Scope for Phase 1 (Agreed):**
   - CAPTCHA solving bypasses (blocked by Akamai Bot Manager; requires 2Captcha/CapSolver API key and modern token injection).
   - Creating 1,000 live accounts (blocked until client provides CAPTCHA solver keys and Phase 2 flow).
   - Full UGPhone / PGTools automated device control (Phase 2 scope — $200).
   - No code will be pushed to remote servers without explicit user approval.

---

## 2. Directory Layout & Key Files

```
KinanCity/
├── PROJECT_MEMORY.md                       ← THIS FILE (Complete Agent & User Context)
├── pom.xml                                 ← Root Maven POM (Java 17, dependency pins)
├── KinanCity-core/                         ← CLI & account creation engine
│   └── target/kinancity-core-2.1.19-SNAPSHOT.jar
├── KinanCity-mail/                         ← Embedded SMTP receiver & link extractor
│   └── target/kinancity-mail-2.1.19-SNAPSHOT.jar
├── ptc-api/                                ← PTC HTTP client & cookie manager
├── KinanCity-captcha-*/                    ← Captcha solver modules (2captcha, capsolver, etc.)
│
├── Documentation/
│   ├── KINANCITY_ARCHITECTURE.md           ← Complete system architecture & Mermaid diagrams
│   ├── KINANCITY_MODERNIZATION_REPORT.md   ← Full modernization changelog & bug fixes
│   ├── MODERNIZATION_NOTES.md              ← Root-cause technical notes
│   ├── SETUP_AND_RUN.md                    ← Windows / Mac setup & execution guide
│   └── PTC_REGISTRATION_INVESTIGATION.md   ← Live probe report on PTC endpoints & Akamai
│
└── python-automation/                      ← Python Backend System
    ├── config.ini                          ← Configuration (ports, retry limits, timeouts)
    ├── accounts.txt.example                ← Tracked template for credentials
    ├── accounts.txt                        ← Git-ignored user credentials (username:password)
    ├── queue_state.json                    ← Git-ignored state machine resume file
    ├── main.py                             ← CLI orchestrator (--dry-run, --status, --investigate)
    ├── account_queue.py                    ← Queue loading, ordering, and resume logic
    ├── account_record.py                   ← AccountRecord dataclass & AccountState enum
    ├── state_machine.py                    ← Lifecycle state engine
    ├── credential_store.py                 ← Secure validation (never logs passwords)
    ├── retry_handler.py                    ← Exponential backoff retry logic
    ├── mail_watcher.py                     ← KinanCity-mail SMTP listener bridge
    ├── ptc_investigator.py                 ← Read-only PTC endpoint diagnostics
    ├── run_logger.py                       ← Structured JSON logger
    ├── adapters/
    │   ├── ugphone_driver.py               ← ADB and Simulated low-level drivers
    │   └── ugphone_adapter.py              ← Full PGTools / UGPhone automation engine
    └── tests/                              ← Unit test suite (39 passing tests)
        ├── test_account_queue.py
        ├── test_credential_store.py
        ├── test_ptc_investigator.py
        ├── test_state_machine.py
        └── test_ugphone_adapter.py
```

---

## 3. Current System State & Test Results

1. **Maven Build & Tests:**
   - `mvn test` → **BUILD SUCCESS** (All 14 modules pass).
   - `mvn package` → **BUILD SUCCESS** (All fat JARs generated in `*/target/`).
2. **Python Unit Tests:**
   - `python3 -m unittest discover -s tests` → **Ran 39 tests in 0.271s: OK** (100% passing).
3. **Phase 2 PGTools Gameplay Loop:**
   - `python3 main.py --dry-run --ugphone` → **Completed 2/2 accounts to COMPLETED state**.
   - Verified lowest-CP-first sort logic to preserve Stardust.
   - Verified automated Candy checking, power-up execution, and quest reward claiming.
4. **PTC Live Investigation:**
   - `https://club.pokemon.com/us/pokemon-trainer-club/sign-up/` redirects (302) to `https://trainer.pokemon.com/profile`.
   - Direct POST without Akamai sensor data returns `403 Forbidden`.
   - Live endpoint probe documentation generated at `Documentation/PTC_REGISTRATION_INVESTIGATION.md`.

---

## 4. How to Test and Run Locally

### Option A: Run Full Python Unit Test Suite (39 Tests)
```bash
cd "python-automation"
python3 -m unittest discover -s tests -v
```
*Expected result:* 39 tests pass (`OK`).

### Option B: Run Full PGTools Automation Simulation
```bash
cd "python-automation"
python3 main.py --dry-run --ugphone
```
*Expected result:* Ingests `accounts.txt`, runs the full PGTools loop on the simulated cloud phone, sorts by lowest CP, completes power-ups, claims rewards, and marks all accounts `COMPLETED` in `queue_state.json`.
1. Create a test `accounts.txt` from the template:
   ```bash
   cd "python-automation"
   cp accounts.txt.example accounts.txt
   echo "TrainerTest01:P@ssw0rd123!" >> accounts.txt
   ```
2. Check queue status:
   ```bash
   python3 main.py --status
   ```
3. Run simulation (dry-run):
   ```bash
   python3 main.py --dry-run
   ```
*This processes accounts through the state machine without making outbound HTTP requests.*

### Option C: Run Local KinanCity-mail Server
The built mail module starts a local SMTP server that receives emails and extracts activation links:
```bash
# From repository root
java -jar KinanCity-mail/target/kinancity-mail-2.1.19-SNAPSHOT.jar
```
*By default, this listens on SMTP port 2525 and writes extracted activation links to `links.log`.*

To test sending a sample email to it locally from Python or netcat:
```python
import smtplib
from email.mime.text import MIMEText

msg = MIMEText("Please activate your account: https://club.pokemon.com/us/pokemon-trainer-club/activated/abc123token")
msg['Subject'] = "Pokemon Trainer Club Activation"
msg['From'] = "noreply@pokemon.com"
msg['To'] = "TrainerTest01@localhost"

with smtplib.SMTP('localhost', 2525) as server:
    server.send_message(msg)
print("Sent test email! Check links.log")
```

### Option D: Run Live PTC Investigation Probe
```bash
cd "python-automation"
python3 ptc_investigator.py
```
*Outputs diagnostics and refreshes `Documentation/PTC_REGISTRATION_INVESTIGATION.md`.*

---

## 5. Phase 2 UGPhone / PGTools Roadmap

When the client approves Phase 2:
1. **UGPhone Cloud Mobile Integration:**
   - Implement `adapters/ugphone_adapter.py` using UGPhone REST API / ADB forwarder.
   - Manage cloud phone boot, app launch, and automated login.
2. **PGTools Automation Flow:**
   - Coordinate states: `PGTOOLS_READY` → `WAIT_CANDY` → `POWERUP` → `QUEST_CHECK` → `REWARD`.
3. **CAPTCHA Solution:**
   - Wire 2Captcha / CapSolver API key into KinanCity captcha modules or Python session handler.
