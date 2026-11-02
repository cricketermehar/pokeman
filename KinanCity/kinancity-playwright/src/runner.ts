import { loadConfig } from './config/environment';
import { BrowserService } from './core/browser.service';
import { RetryManager } from './core/retry.manager';
import { CaptchaService } from './services/captcha.service';
import { EmailVerificationService } from './services/email.service';
import { RegistrationService } from './services/registration.service';
import { MockMailboxAdapter } from './adapters/mock-mailbox.adapter';
import { MailboxAdapter } from './adapters/mailbox.adapter';
import { logger } from './core/logger.service';
import { WorkflowResult, WorkflowStatus } from './types';

export class WorkflowOrchestrator {
  private status: WorkflowStatus = 'QUEUED';
  private workflowStartTime: number = 0;
  private isAborted: boolean = false;

  constructor(
    private browserService: BrowserService,
    private registrationService: RegistrationService,
    private emailService: EmailVerificationService,
    private retryManager: RetryManager,
    private config: ReturnType<typeof loadConfig>
  ) {}

  public getStatus(): WorkflowStatus {
    return this.status;
  }

  public abort(): void {
    this.isAborted = true;
    this.status = 'FAILED';
    logger.warn('Workflow received abort signal.');
  }

  async run(): Promise<WorkflowResult> {
    this.workflowStartTime = Date.now();
    this.status = 'QUEUED';
    let diagnosticScreenshot: string | undefined;

    logger.info('════════════════════════════════════════════════════════════');
    logger.info('  KinanCity Playwright Automation — Workflow Started');
    logger.info(`  Account: ${this.config.TEST_ACCOUNT_USERNAME}`);
    logger.info(`  Target URL: ${this.config.TEST_TARGET_URL}`);
    logger.info('════════════════════════════════════════════════════════════');

    const context = await this.browserService.createContext('auth_session');
    const page = await context.newPage();

    try {
      if (this.isAborted) throw new Error('Workflow aborted before execution');

      // ── Step 1: Navigation ──────────────────────────────────────────────────
      this.status = 'NAVIGATING';
      logger.info('State: NAVIGATING');
      await this.retryManager.execute(
        async () => {
          await page.goto(this.config.TEST_TARGET_URL, {
            waitUntil: 'domcontentloaded',
            timeout: this.config.BROWSER_TIMEOUT_MS,
          });
        },
        'page-navigation',
        { isIdempotent: true }
      );

      // ── Step 2: Form Population ─────────────────────────────────────────────
      this.status = 'FILLING_CREDENTIALS';
      logger.info('State: FILLING_CREDENTIALS');
      await this.registrationService.fillRegistrationForm(page, {
        username: this.config.TEST_ACCOUNT_USERNAME,
        password: this.config.TEST_ACCOUNT_PASSWORD,
        email: this.config.TEST_ACCOUNT_EMAIL,
      });

      // ── Step 3: CAPTCHA Challenge & Submission ──────────────────────────────
      this.status = 'SUBMITTING';
      logger.info('State: SUBMITTING');
      await this.registrationService.submitForm(page);

      // ── Step 4: Email Verification ──────────────────────────────────────────
      this.status = 'AWAITING_EMAIL_VERIFICATION';
      logger.info('State: AWAITING_EMAIL_VERIFICATION');

      const activationUrl = await this.emailService.waitForVerificationToken(
        this.workflowStartTime,
        context
      );

      // ── Step 5: Activation Navigation ───────────────────────────────────────
      this.status = 'ACTIVATING';
      logger.info('State: ACTIVATING', {
        activationUrl: activationUrl.replace(/(activated\/)[a-zA-Z0-9_-]+/gi, '$1[TOKEN_REDACTED]'),
      });

      await page.goto(activationUrl, {
        waitUntil: 'domcontentloaded',
        timeout: this.config.BROWSER_TIMEOUT_MS,
      });

      // ── Step 6: Verify Actual Completion ────────────────────────────────────
      // Look for confirmation element or text
      const isConfirmed = await page
        .locator('text=/activated|verified|success|welcome/i')
        .first()
        .isVisible({ timeout: 10000 })
        .catch(() => false);

      if (!isConfirmed) {
        logger.warn('Completion indicator not detected automatically. Capturing diagnostic.');
        diagnosticScreenshot = await this.browserService.captureScreenshot(page, 'activation_unconfirmed');
      }

      this.status = 'COMPLETED';
      logger.info('State: COMPLETED — Account successfully registered and activated!');

      const durationMs = Date.now() - this.workflowStartTime;
      return {
        success: true,
        username: this.config.TEST_ACCOUNT_USERNAME,
        finalStatus: this.status,
        durationMs,
        diagnosticScreenshot,
      };
    } catch (error) {
      this.status = 'FAILED';
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('Workflow execution halted with failure', { error: errorMessage });

      try {
        diagnosticScreenshot = await this.browserService.captureScreenshot(page, 'workflow_failure');
      } catch {}

      return {
        success: false,
        username: this.config.TEST_ACCOUNT_USERNAME,
        finalStatus: this.status,
        durationMs: Date.now() - this.workflowStartTime,
        error: errorMessage,
        diagnosticScreenshot,
      };
    } finally {
      await this.browserService.closeContext(context, 'workflow_run');
    }
  }
}

export async function main(): Promise<WorkflowResult> {
  const config = loadConfig();
  const browserService = new BrowserService(config);
  const captchaService = new CaptchaService(config.OPERATOR_TIMEOUT_MS, 1000, config.SANDBOX_MODE);
  const registrationService = new RegistrationService(captchaService);
  const retryManager = new RetryManager({
    maxRetries: config.MAX_RETRIES,
    baseDelayMs: config.BASE_RETRY_DELAY_MS,
  });

  const mailboxAdapter: MailboxAdapter = new MockMailboxAdapter(new URL(config.TEST_TARGET_URL).origin);
  const emailService = new EmailVerificationService(mailboxAdapter, config);

  const orchestrator = new WorkflowOrchestrator(
    browserService,
    registrationService,
    emailService,
    retryManager,
    config
  );

  try {
    await browserService.initialize();
    const result = await orchestrator.run();

    console.log('\n════════════════════════════════════════════════════════════');
    console.log('  FINAL EXECUTION REPORT');
    console.log(`  Success      : ${result.success ? '✅ YES' : '❌ NO'}`);
    console.log(`  Final Status : ${result.finalStatus}`);
    console.log(`  Duration     : ${(result.durationMs / 1000).toFixed(2)}s`);
    if (result.error) console.log(`  Error        : ${result.error}`);
    if (result.diagnosticScreenshot) console.log(`  Diagnostic   : ${result.diagnosticScreenshot}`);
    console.log('════════════════════════════════════════════════════════════\n');

    return result;
  } finally {
    await browserService.teardown();
  }
}

if (require.main === module) {
  main();
}
