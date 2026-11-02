# KinanCity Playwright Automation Framework (v2.0.0)

A modernized, high-reliability, and secure TypeScript + Playwright automation framework for authorized account-workflow validation, testing, and lifecycle monitoring.

---

## 1. Prerequisites

- **Node.js:** v18.0.0 or later (v20+ recommended)
- **npm:** v9.0.0 or later
- **Operating Systems:** macOS (Intel / Apple Silicon) and Linux (Ubuntu 20.04+, Debian, Fedora, Arch)

---

## 2. Quick Start & Installation

### Step 1: Install Dependencies
```bash
npm install
```

### Step 2: Install Playwright Chromium Browser & OS Dependencies
```bash
npx playwright install chromium

# On Linux (Ubuntu/Debian), install required system libraries:
# npx playwright install-deps chromium
```

### Step 3: Configure Environment
Copy the example environment configuration:
```bash
cp .env.example .env
```
Edit `.env` to configure your test parameters (defaults are pre-configured for the local testbed).

### Step 4: Build TypeScript Source
```bash
npm run build
```

---

## 3. Running Tests

The test suite includes comprehensive unit tests, integration tests against isolated browser contexts, and full end-to-end workflow validation against the local fixture application.

Execute all tests:
```bash
npm test
```

Execute unit tests only:
```bash
npx playwright test tests/unit/
```

Execute integration and E2E tests:
```bash
npx playwright test tests/integration/ tests/e2e/
```

View the detailed interactive HTML report:
```bash
npm run test:report
```

---

## 4. Running the Local Testbed Application

You can launch the standalone testbed web server on port 3000 to observe the registration form, sandbox challenge widget, and activation flow:
```bash
npm run testbed
```
Then navigate to: `http://localhost:3000/signup` in your browser.

---

## 5. Workflow Execution & Scripts

| Command | Description |
| :--- | :--- |
| `npm run build` | Compiles TypeScript codebase (`tsc`) with zero errors. |
| `npm test` | Runs the full Playwright test suite (33 tests). |
| `npm start` | Executes the main workflow runner (`src/runner.ts`). |
| `npm run testbed` | Launches the local HTTP test application fixture. |
| `npm run session:proton` | Interactive Human-in-the-Loop script to authenticate and securely save Proton Mail session state. |

---

## 6. Directory Structure

```
kinancity-playwright/
├── .env.example              # Baseline environment configuration template
├── .gitignore                # Excludes secrets, credentials, logs, and traces
├── README.md                 # Project documentation and quickstart
├── package.json              # Project dependencies and script definitions
├── tsconfig.json             # TypeScript strict compilation configuration
├── playwright.config.ts      # Playwright test runner configuration
├── src/
│   ├── config/
│   │   └── environment.ts    # Zod schema validation & security origin checks
│   ├── core/
│   │   ├── browser.service.ts # Playwright browser lifecycle & diagnostics
│   │   ├── session.manager.ts # Storage state validation & 0600 permissions
│   │   ├── retry.manager.ts   # Exponential backoff with jitter
│   │   └── logger.service.ts  # Structured JSON logging with deep redaction
│   ├── services/
│   │   ├── captcha.service.ts # Challenge detection & HITL pause/resume
│   │   ├── email.service.ts   # Activation link extraction & allowlist validation
│   │   └── registration.service.ts # Resilient form population & submission
│   ├── adapters/
│   │   ├── mailbox.adapter.ts      # Mailbox provider interface
│   │   └── mock-mailbox.adapter.ts # Test mock mailbox adapter
│   ├── scripts/
│   │   └── initProtonSession.ts    # Interactive Proton Mail session creator
│   ├── types/
│   │   └── index.ts                # TypeScript interfaces, enums, and types
│   └── runner.ts                   # Workflow state machine orchestrator
├── fixtures/
│   └── test-app/
│       └── server.ts         # Local controlled testbed web server
├── tests/
│   ├── unit/                 # Environment, logger, retry, session, captcha tests
│   ├── integration/          # Browser context and registration tests
│   └── e2e/                  # Full end-to-end workflow orchestration tests
├── docs/
│   ├── audit-report.md       # Comprehensive code audit and issue matrix
│   ├── architecture.md       # Architectural diagrams and design specifications
│   ├── security.md           # Security boundary, secrets management, and SSRF defense
│   └── troubleshooting.md    # Common operational errors and remediation
├── logs/                     # Auto-generated diagnostic screenshots and traces
└── sessions/                 # Restricted 0600 storage states (gitignored)
```

---

## 7. Security Boundaries & Compliance

- **No CAPTCHA Bypassing:** Automatic bypass algorithms are strictly prohibited and omitted. The service supports Human-in-the-Loop operator resolution and official sandbox keys.
- **Credential Protection:** Passwords and verification tokens are never stored in git or printed in logs.
- **SSRF Defense:** All external links and email activation URLs are strictly gated by `ALLOWED_ORIGINS`.
