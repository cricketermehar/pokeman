# SETUP AND RUN GUIDE

## Environment Requirements

| Requirement | Version | Notes |
|---|---|---|
| Operating System | Windows 11 | Tested on Windows 11 Pro |
| Java | 17 (Temurin OpenJDK 17.0.x) | Required for KinanCity JAR |
| Maven | 3.9+ | Required to build from source |
| Python | 3.10+ | Required for automation backend |
| pip | Latest | For Python dependencies |

---

## Part 1 — Java Build (KinanCity)

### Step 1 — Clone and switch to the modernization branch

```powershell
git clone https://github.com/drallieiv/KinanCity.git
cd KinanCity
git checkout modernization/build-restore
```

### Step 2 — Build

```powershell
mvn clean test
mvn clean package
```

Expected output:
```
BUILD SUCCESS
Tests run: 67, Failures: 0, Errors: 0, Skipped: 12
```

### Step 3 — AVG antivirus workaround (Windows only)

If Maven fails with certificate errors due to AVG Web Shield:

```powershell
$env:MAVEN_OPTS="-Djavax.net.ssl.trustStoreType=Windows-ROOT"
mvn clean test
mvn clean package
```

> This is a local environment workaround — do not commit it.

### Step 4 — Build artifacts

After a successful `mvn clean package`:

| File | Location |
|---|---|
| KinanCity core JAR | `KinanCity-core/target/kinancity-core-2.1.19-SNAPSHOT.jar` |
| KinanCity mail JAR | `KinanCity-mail/target/kinancity-mail-2.1.19-SNAPSHOT.jar` |
| CAPTCHA server JAR | `KinanCity-captcha-server/target/kinancity-captcha-server-*.jar` |
| ZIP distributions | `*/target/*.zip` |

---

## Part 2 — KinanCity-mail (Email Activation Server)

KinanCity-mail is a local SMTP server that receives activation emails and extracts links.

### Run in log mode (safe — no outbound requests)

```powershell
java -jar KinanCity-mail\target\kinancity-mail-2.1.19-SNAPSHOT.jar log
```

This starts an SMTP server on port `2525` and writes activation links to `links.log`.

### Test with a local email

Use any SMTP client (Swaks, Thunderbird, telnet) to send a test email to `127.0.0.1:2525`.

```bash
# Linux/Mac test (Swaks)
swaks --to test@yourdomain.com --server 127.0.0.1:2525
```

Check `links.log` for the extracted activation link.

### What KinanCity-mail is NOT

KinanCity-mail is an **SMTP receiving server**, not an IMAP/POP mail client.  
Do not enter your Proton Mail credentials directly into it.

To use it with Proton Mail:
1. Configure Proton Mail Bridge or a mail relay to forward incoming mail to `127.0.0.1:2525`.
2. Or point the PTC registration email at a domain you control with an MX record pointing to your machine.

---

## Part 3 — Python Automation Backend

### Step 1 — Navigate to the python-automation folder

```powershell
cd python-automation
```

### Step 2 — Create a virtual environment (recommended)

```powershell
python -m venv venv
venv\Scripts\activate
```

### Step 3 — Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 4 — Create accounts.txt

Create `python-automation/accounts.txt` with your accounts:

```
# My accounts
TrainerJason01:YourP@ssw0rd1
TrainerJason02:YourP@ssw0rd2
```

> ⚠️ This file is `.gitignore`d — it will never be committed.

### Step 5 — Edit config.ini

Open `config.ini` and set your email address:

```ini
email = Counterass100@proton.me
```

Leave all other settings at their defaults for the first run.

### Step 6 — Run the PTC investigator (first time)

```powershell
python main.py --investigate
```

This probes the current PTC registration flow and writes:
```
Documentation/PTC_REGISTRATION_INVESTIGATION.md
```

Read this report before attempting any account creation.

### Step 7 — Dry run (safe — no real HTTP calls)

```powershell
python main.py --dry-run
```

This drives every account through the state machine with stub handlers.  
Confirms your accounts.txt is formatted correctly and queue logic works.

### Step 8 — Check status

```powershell
python main.py --status
```

Shows current state of every account.

### Step 9 — Real run

```powershell
python main.py
```

Processes all QUEUED accounts. Progress is saved to `queue_state.json` after each account.  
If interrupted, re-running resumes from where it left off.

### Step 10 — Reset a failed account

```powershell
python main.py --reset TrainerJason01
```

Resets that account to QUEUED so it will be processed again on the next run.

---

## Part 4 — Run Tests

```powershell
cd python-automation
python -m pytest tests/ -v
```

Expected:
```
PASSED tests/test_account_queue.py::...
PASSED tests/test_state_machine.py::...
PASSED tests/test_credential_store.py::...
PASSED tests/test_ptc_investigator.py::...
```

---

## Security Checklist

Before each run, verify:

- [ ] `accounts.txt` is not committed to Git
- [ ] `queue_state.json` is not committed to Git
- [ ] `links.log` is not committed to Git
- [ ] `result.csv` is not committed to Git
- [ ] No passwords in `config.ini`
- [ ] No passwords visible in terminal history (use config file, not CLI `-p`)

---

## File Structure Reference

```
KinanCity/
├── python-automation/
│   ├── accounts.txt          ← GITIGNORED — your credentials here
│   ├── queue_state.json      ← GITIGNORED — auto-generated
│   ├── config.ini            ← non-secret settings
│   ├── main.py               ← entry point
│   ├── account_queue.py      ← queue manager
│   ├── account_record.py     ← data model + state enum
│   ├── state_machine.py      ← per-account lifecycle
│   ├── credential_store.py   ← secure file loader
│   ├── ptc_investigator.py   ← PTC flow probe
│   ├── mail_watcher.py       ← links.log → queue bridge
│   ├── retry_handler.py      ← exponential backoff
│   ├── run_logger.py         ← per-run logging
│   ├── requirements.txt
│   ├── adapters/
│   │   └── ugphone_adapter.py  ← Phase 2 stub
│   └── tests/
│       ├── test_account_queue.py
│       ├── test_state_machine.py
│       ├── test_credential_store.py
│       └── test_ptc_investigator.py
├── Documentation/
│   ├── KINANCITY_MODERNIZATION_REPORT.md
│   ├── KINANCITY_ARCHITECTURE.md
│   ├── MODERNIZATION_NOTES.md
│   ├── SETUP_AND_RUN.md          ← this file
│   └── PTC_REGISTRATION_INVESTIGATION.md  ← auto-generated
└── README.md
```
