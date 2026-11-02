# KinanCity Playwright Troubleshooting Guide

## Common Issues & Resolutions

### 1. "Security Challenge Detected: Pausing for Human-in-the-Loop..."
- **Cause:** The target page displayed an interactive security challenge (reCAPTCHA, Cloudflare Turnstile, or hCaptcha).
- **Resolution:**
  - If running locally with `HEADLESS=false`, switch to the browser window and complete the puzzle manually.
  - When verified, the automation detects the populated response token and automatically resumes.
  - In automated CI test pipelines, use the mock fixture (`npm test`), which runs against `fixtures/test-app/server.ts` with sandbox test keys.

### 2. "Configuration Validation Error: Target URL origin is not in configured ALLOWED_ORIGINS"
- **Cause:** You attempted to run the runner against a domain that is not included in your `.env` `ALLOWED_ORIGINS` list.
- **Resolution:**
  - Add your test domain to `ALLOWED_ORIGINS` in `.env`:
    ```ini
    ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001,https://authorized-testbed.example.com
    ```

### 3. "Refusing to execute registration workflow against production domain without explicit authorization"
- **Cause:** The workflow was pointed at a live domain (e.g. `trainer.pokemon.com`) while `ALLOW_PRODUCTION_REGISTRATION=false`.
- **Resolution:**
  - For safety against unintentional bulk submissions, live execution is locked.
  - For authorized testing on client staging/production environments, explicitly configure in `.env`:
    ```ini
    ALLOW_PRODUCTION_REGISTRATION=true
    ```

### 4. "Email verification message did not arrive within timeout"
- **Cause:** The mailbox adapter did not receive a matching message within `OPERATOR_TIMEOUT_MS`.
- **Resolution:**
  - Check that the email address configured in `TEST_ACCOUNT_EMAIL` matches the incoming test message.
  - Verify that the message timestamp is newer than the workflow start time (stale messages are rejected by design).
  - Increase `OPERATOR_TIMEOUT_MS` in `.env` if external email deliverability is delayed.

### 5. "Corrupted JSON session file or all session cookies have expired"
- **Cause:** The cached session in `sessions/` has expired or the file was truncated.
- **Resolution:**
  - Invalidate the session: `rm sessions/*_storage_state.json`.
  - Re-run the interactive session initializer:
    ```bash
    npm run session:proton
    ```

### 6. "tracing.start: Tracing has been already started"
- **Cause:** Playwright Test runner and custom browser instances collided on tracing triggers.
- **Resolution:**
  - Resolved in `v2.0.0` by isolating `BrowserService` tracing lifecycle and setting `trace: 'off'` in `playwright.config.ts`.
