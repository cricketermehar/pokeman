# KinanCity Modernization & Bug Fix Notes

**Branch:** `modernization/build-restore`  
**Base Commit:** `d5ff626` (develop)  
**Date:** October 2026  

---

## 1. Build Restoration & Dependency Modernization

### 1.1 Root `pom.xml` & Compiler Settings
* **Issue:** Legacy build targeted Java 8/1.8 with outdated compiler plugins and broken dependency management.
* **Fix:** 
  - Standardized root compiler plugin configuration to Java 17 (`source: 17`, `target: 17`).
  - Added dependency management across all modules to enforce consistent versions.
  - Resolved Maven Surefire and plugin management compatibility for Java 17.

### 1.2 OkHttp Duplicate Dependency Conflict
* **Issue:** Multiple modules had conflicting versions of OkHttp and Okio (e.g. OkHttp 2.x and OkHttp 3.x transitive dependencies), causing class shadowing and runtime linkage errors (`NoClassDefFoundError` / `NoSuchMethodError`).
* **Fix:**
  - Standardized on OkHttp 3.14.9 across all child modules (`ptc-api`, `KinanCity-core`, `KinanCity-mail`).
  - Excluded legacy conflicting OkHttp artifacts in transitive dependency trees.

---

## 2. Security & Credential Redaction Fixes

### 2.1 Plaintext Credentials in Logs
* **Issue:** In `PtcSession.java`, `KinanCityCli.java`, and `PtcAccountCreator.java`, account passwords and HTTP proxy credentials were printed directly to `System.out` and SLF4J log streams during registration attempts and proxy setup.
* **Fix:**
  - In `PtcSession.java`: Replaced raw password string dumps in logs with `[PROTECTED]` or truncated masked representations.
  - In `KinanCityCli.java`: Masked CLI arguments when outputting runtime configurations.
  - In `HttpProxy.java`: Sanitized proxy authentication string representations to mask proxy credentials.

---

## 3. KinanCity-mail Module Improvements

### 3.1 MIME Parsing & Activation Link Extraction
* **Issue:** The SubEthaSMTP receiver in `KinanCity-mail` failed when handling single-part plain-text email bodies or specific MIME multipart encodings. The activation link extraction regex also failed on modern PTC URL structures containing trailing parameters or URL encoding.
* **Fix:**
  - Updated `DirectLinkActivator.java` and email parsing logic to handle both single-part and multipart MIME messages gracefully.
  - Updated the link extractor regex to match modern activation URL patterns (`https://club.pokemon.com/...` and `https://trainer.pokemon.com/...`).
  - Added safe retry logic on transient network or connection timeouts during link activation verification.

---

## 4. Python Automation Backend Design Rationale

### 4.1 Modular Architecture
* **State Machine (`state_machine.py`):**
  - Manages clear lifecycle transitions for every account.
  - Distinguishes new account flow (`QUEUED -> LOGIN_PENDING -> PTC_REGISTRATION -> AWAITING_ACTIVATION -> COMPLETED`) from existing accounts (`PGTOOLS_READY -> WAIT_CANDY -> POWERUP -> QUEST_CHECK -> REWARD`).
  - Failure states (`FAILED_LOGIN`, `ACTIVATION_TIMEOUT`, `MANUAL_REQUIRED`) trigger exponential backoff via `RetryHandler` before escalating to manual intervention.
* **Zero Credential Exposure:**
  - `accounts.txt` is read on demand by `CredentialStore`.
  - Passwords are strictly kept in memory and never written to `queue_state.json` or run logs.
* **Extensibility for Phase 2:**
  - Cloud mobile automation for UGPhone / PGTools is cleanly decoupled into `adapters/ugphone_adapter.py`.
