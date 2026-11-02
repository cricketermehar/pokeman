# KinanCity Modernization Report

**Project:** KinanCity 2.1.19-SNAPSHOT — Build Restoration & Security Fixes  
**Branch:** `modernization/build-restore`  
**Base commit:** `d5ff626` (develop)  
**Date:** October 2026

---

## 1. Summary

The legacy KinanCity project (last released v2.1.18) failed to build under Maven 3.10 and Java 17 due to a duplicate dependency declaration and open-ended version ranges. This report documents all changes made to restore the build, fix security issues, fix the mail module, and add a Python automation backend.

---

## 2. Build Problems Fixed

### 2.1 Duplicate OkHttp Dependency (BLOCKING)

**File:** `KinanCity-mail/pom.xml`

The file declared `okhttp` twice:
```xml
<version>4.9.1</version>   ← kept
<version>4.1.0</version>   ← REMOVED
```

Maven 3.10 rejects duplicate dependency declarations. Removing the `4.1.0` declaration restored the build.

### 2.2 Open-Ended Version Ranges (REPRODUCIBILITY)

**File:** `pom.xml` (parent)

Replaced open-ended ranges with fixed versions:
```
jackson-databind:  [2.9.10.5,)  →  2.13.4.2
commons-collections4:  [4.1,)  →  4.4
```

Open ranges allow Maven to silently select different versions on future builds, breaking reproducibility.

---

## 3. Security Fixes

### 3.1 Password Logged in Plain Text

**File:** `ptc-api/src/main/java/com/kinancity/api/PtcSession.java`

Original:
```java
logger.error("Invalid password '{}' ...", password);
```
Fixed:
```java
logger.error("Invalid password for account '{}' (length={}) ...", username, password.length());
```

### 3.2 CLI Password Argument Logged

**File:** `KinanCity-core/src/main/java/com/kinancity/core/KinanCityCli.java`

The startup log printed all CLI args verbatim, exposing `-p <password>`.

Fixed: args are cloned and any value following `-p` or `--password` is replaced with `[MASKED]` before logging.

### 3.3 Proxy Credentials in toString()

**File:** `KinanCity-core/src/main/java/com/kinancity/core/proxy/impl/HttpProxy.java`

`toURI()` / `toString()` returned `protocol://login:password@host:port`.
Any `logger.debug("proxy: {}", proxy)` call exposed the proxy password.

Fixed: password replaced with `***` in the URI representation.

### 3.4 Account Passwords in End-of-Run Log

**File:** `KinanCity-core/src/main/java/com/kinancity/core/PtcAccountCreator.java`

The RocketMap-format end-of-run dump logged `ptc,username,password` for every created account.

Fixed: passwords replaced with `[password-in-result.csv]` in the log. The actual credentials remain in `result.csv` (intentional — but `result.csv` is gitignored).

---

## 4. KinanCity-mail Fixes

### 4.1 HTTP Client Never Initialised (CRITICAL BUG)

**File:** `KinanCity-mail/src/main/java/com/kinancity/mail/activator/DirectLinkActivator.java`

The constructor built an `OkHttpClient` but **discarded the result** (didn't assign to `this.client`).  
Every HTTP call threw `NullPointerException`.

Fixed:
```java
// Before (broken):
new OkHttpClient.Builder().readTimeout(...).build();

// After (fixed):
this.client = new OkHttpClient.Builder().readTimeout(...).build();
```

### 4.2 Invalid ConnectionPool Configuration

The original `DirectLinkActivator` used `new ConnectionPool(0, 0, TimeUnit.SECONDS)` which rejects all connections. Removed — default connection pool is now used.

### 4.3 Infinite Loop in main()

The original `main()` method looped forever calling `activateLink()`. Fixed to run once and exit.

---

## 5. Build Verification

After all fixes:

```
mvn clean test
→ BUILD SUCCESS
   Tests run: 67, Failures: 0, Errors: 0, Skipped: 12

mvn clean package
→ BUILD SUCCESS
   14/14 reactor projects
```

---

## 6. Python Automation Backend Added

A complete Python automation backend was added at `python-automation/`.

See `SETUP_AND_RUN.md` for usage instructions.

**Files created:**

| File | Purpose |
|---|---|
| `account_record.py` | AccountRecord dataclass + AccountState enum |
| `account_queue.py` | Ordered, resumable queue with JSON persistence |
| `credential_store.py` | Secure accounts.txt loader (no password logging) |
| `state_machine.py` | Per-account lifecycle driver |
| `retry_handler.py` | Exponential backoff (3×, 60s base) |
| `run_logger.py` | Per-run log file + JSON summary |
| `mail_watcher.py` | links.log poller → queue state updater |
| `ptc_investigator.py` | Read-only PTC flow probe + report generator |
| `adapters/ugphone_adapter.py` | Phase 2 UGPhone stub (interface only) |
| `main.py` | CLI entry point |
| `config.ini` | Non-secret configuration |
| `accounts.txt` | Template (gitignored) |
| `requirements.txt` | Python dependencies |
| `tests/` | 4 test files covering all modules |

---

## 7. Current Registration Status

The legacy KinanCity registration code targets `club.pokemon.com` URLs that now redirect to `trainer.pokemon.com`. This is a **new implementation task**, not a simple URL change.

**Current verified state:**

| Item | Status |
|---|---|
| Legacy build | ✅ PASS |
| Legacy tests (67) | ✅ PASS |
| Current PTC registration | ❌ NOT IMPLEMENTED |
| 1,000 accounts created | ❌ NOT COMPLETED |
| Activation flow verified | ❌ NOT VERIFIED |

---

## 8. What Was Intentionally Not Changed

- `result.csv` output — intentional application behaviour, gitignored
- CAPTCHA solver modules — existing modules retained as-is
- Proxy rate-limit logic — not modified
- Anti-abuse bypass — not implemented (documented as Phase 2 blocker)
