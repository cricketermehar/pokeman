# Security & Compliance Model — KinanCity Modernization

## 1. Security Baseline & Ethical Boundaries

The modernization of KinanCity is designed strictly for **authorized testing, QA automation, and validation in controlled environments**.

### Absolute Security Prohibitions:
1. **No CAPTCHA Bypassing:** The framework contains no algorithms, third-party solver APIs, or scripts designed to circumvent CAPTCHA challenges automatically.
2. **No Bot Detection Evasion:** Hardcoded stealth tampering, canvas spoofing, user-agent forgery, or fingerprint manipulation are explicitly omitted.
3. **No Unauthorized Bulk Registration:** Workflows default to controlled local fixtures. Attempting to run bulk creation against third-party production infrastructure is blocked by default via `ALLOW_PRODUCTION_REGISTRATION=false`.

---

## 2. Secrets & Credential Management

- **Zero Hardcoding:** No passwords, API keys, or session tokens exist in source code, commit history, or test fixtures.
- **Environment Ingestion:** Variables are loaded strictly through `.env` and validated by Zod at startup.
- **Validation Sanitization:** When environment validation fails, passwords and sensitive strings are masked before error messages are emitted.
- **Automated Redaction:** The structured logger (`src/core/logger.service.ts`) recursively redacts sensitive keys:
  - `password`, `secret`, `token`, `cookie`, `auth`, `authorization`, `code`, `activationurl`
- **Activation Token Masking:** Full URLs containing activation tokens are sanitized in diagnostic logs (e.g. `https://example.com/activated/[TOKEN_REDACTED]`).

---

## 3. Session & File Security

- **Strict POSIX Permissions:** All storage state artifacts are saved with `0600` permissions (read/write for owner only). Directory permissions default to `0700`.
- **Git Protection:** `.gitignore` explicitly prevents committing:
  - `.env`
  - `sessions/*.json`
  - `logs/`
  - `playwright-report/`
  - `test-results/`
- **Path Traversal Defense:** Session identifiers are sanitized with strict character whitelisting (`[^a-zA-Z0-9_-]`), neutralizing any `../` directory traversal attempts.

---

## 4. Network Security & SSRF Defense

- **Origin Allowlists (`ALLOWED_ORIGINS`):** Any target URL or email activation link is parsed and evaluated against explicit allowlists. Malicious activation links pointing to external or phishing domains are immediately rejected.
- **Strict TLS:** Context creation sets `ignoreHTTPSErrors: false`, preventing man-in-the-middle attacks on untrusted certificates.
