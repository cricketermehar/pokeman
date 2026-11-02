import { test, expect } from '@playwright/test';
import { startTestApp, TestAppServer } from '../../fixtures/test-app/server';
import { BrowserService } from '../../src/core/browser.service';
import { CaptchaService } from '../../src/services/captcha.service';
import { RegistrationService } from '../../src/services/registration.service';
import { EmailVerificationService } from '../../src/services/email.service';
import { MockMailboxAdapter } from '../../src/adapters/mock-mailbox.adapter';
import { RetryManager } from '../../src/core/retry.manager';
import { WorkflowOrchestrator } from '../../src/runner';
import { loadConfig } from '../../src/config/environment';

test.describe('End-to-End Workflow Orchestration', () => {
  let server: TestAppServer;
  let browserService: BrowserService;
  let mockMailbox: MockMailboxAdapter;
  const testPort = 3002;

  test.beforeAll(async () => {
    server = await startTestApp(testPort);
  });

  test.afterAll(async () => {
    await server.close();
  });

  test('executes complete end-to-end registration and activation workflow', async () => {
    const config = loadConfig({
      TEST_TARGET_URL: `http://localhost:${testPort}/signup`,
      ALLOWED_ORIGINS: `http://localhost:${testPort}`,
      TEST_ACCOUNT_USERNAME: 'MasterTrainerE2E',
      TEST_ACCOUNT_EMAIL: 'e2e_trainer@example.com',
      HEADLESS: 'true',
      OPERATOR_TIMEOUT_MS: '6000',
    });

    browserService = new BrowserService(config);
    await browserService.initialize();

    const captchaService = new CaptchaService(5000, 300, true);
    const registrationService = new RegistrationService(captchaService);
    mockMailbox = new MockMailboxAdapter();
    const emailService = new EmailVerificationService(mockMailbox, config);
    const retryManager = new RetryManager({ maxRetries: 2, baseDelayMs: 100 });

    const orchestrator = new WorkflowOrchestrator(
      browserService,
      registrationService,
      emailService,
      retryManager,
      config
    );

    // Schedule background task to simulate human verification of challenge & dispatch incoming email
    const solveTask = setTimeout(async () => {
      // In a real sandbox or HITL scenario, the response token gets filled
      const contexts = browserService.getActiveContexts();
      for (const ctx of contexts) {
        for (const pg of ctx.pages()) {
          try {
            const btn = pg.locator('#sandbox-solve-btn');
            if (await btn.isVisible()) {
              await btn.click();
            }
          } catch {}
        }
      }

      // Simulate email arriving 1 second after registration
      setTimeout(() => {
        const token = server.lastGeneratedToken || 'mock_activation_token_123';
        mockMailbox.pushMessage({
          id: 'msg-e2e-1',
          recipient: config.TEST_ACCOUNT_EMAIL,
          sender: 'noreply@pokemon.com',
          subject: 'Activate Your Pokémon Trainer Club Account',
          activationUrl: `http://localhost:${testPort}/profile/activated/${token}`,
          timestamp: Date.now(),
        });
      }, 1000);
    }, 1500);

    const result = await orchestrator.run();
    clearTimeout(solveTask);

    expect(result.success).toBe(true);
    expect(result.finalStatus).toBe('COMPLETED');
    expect(result.username).toBe('MasterTrainerE2E');
    expect(result.durationMs).toBeGreaterThan(0);

    await browserService.teardown();
  });

  test('halts safely with diagnostic capture when CAPTCHA challenge is not resolved', async () => {
    const config = loadConfig({
      TEST_TARGET_URL: `http://localhost:${testPort}/signup`,
      ALLOWED_ORIGINS: `http://localhost:${testPort}`,
      TEST_ACCOUNT_USERNAME: 'TimeoutTrainer',
      TEST_ACCOUNT_EMAIL: 'timeout@example.com',
      HEADLESS: 'true',
      OPERATOR_TIMEOUT_MS: '1500',
    });

    browserService = new BrowserService(config);
    await browserService.initialize();

    // Short operator timeout to simulate abandoned or failed challenge
    const captchaService = new CaptchaService(1200, 200);
    const registrationService = new RegistrationService(captchaService);
    mockMailbox = new MockMailboxAdapter();
    const emailService = new EmailVerificationService(mockMailbox, config);
    const retryManager = new RetryManager({ maxRetries: 1, baseDelayMs: 100 });

    const orchestrator = new WorkflowOrchestrator(
      browserService,
      registrationService,
      emailService,
      retryManager,
      config
    );

    // Notice we do NOT solve the challenge here
    const result = await orchestrator.run();

    expect(result.success).toBe(false);
    expect(result.finalStatus).toBe('FAILED');
    expect(result.error).toContain('Registration blocked by challenge');
    expect(result.diagnosticScreenshot).toBeDefined();

    await browserService.teardown();
  });

  test('security guard: rejects malicious activation links outside ALLOWED_ORIGINS', async () => {
    const config = loadConfig({
      TEST_TARGET_URL: `http://localhost:${testPort}/signup`,
      ALLOWED_ORIGINS: `http://localhost:${testPort}`,
      TEST_ACCOUNT_USERNAME: 'PhishGuard99',
      TEST_ACCOUNT_EMAIL: 'phish_guard@example.com',
      HEADLESS: 'true',
      OPERATOR_TIMEOUT_MS: '5000',
    });

    browserService = new BrowserService(config);
    await browserService.initialize();

    const captchaService = new CaptchaService(4000, 200, true);
    const registrationService = new RegistrationService(captchaService);
    mockMailbox = new MockMailboxAdapter();
    const emailService = new EmailVerificationService(mockMailbox, config);
    const retryManager = new RetryManager({ maxRetries: 1, baseDelayMs: 100 });

    const orchestrator = new WorkflowOrchestrator(
      browserService,
      registrationService,
      emailService,
      retryManager,
      config
    );

    const solveTask = setTimeout(async () => {
      const contexts = browserService.getActiveContexts();
      for (const ctx of contexts) {
        for (const pg of ctx.pages()) {
          try {
            const btn = pg.locator('#sandbox-solve-btn');
            if (await btn.isVisible()) {
              await btn.click();
            }
          } catch {}
        }
      }

      // Inject malicious phishing activation link (e.g. spoofed sender or attacker payload)
      setTimeout(() => {
        mockMailbox.pushMessage({
          id: 'msg-phish-1',
          recipient: config.TEST_ACCOUNT_EMAIL,
          sender: 'security@pokemon.com',
          subject: 'Activate Your Account',
          activationUrl: 'http://malicious-phishing-site.com/profile/activated/stolen_token',
          timestamp: Date.now(),
        });
      }, 800);
    }, 1000);

    const result = await orchestrator.run();
    clearTimeout(solveTask);

    expect(result.success).toBe(false);
    expect(result.finalStatus).toBe('FAILED');
    expect(result.error).toContain('Security Violation: Activation URL origin');

    await browserService.teardown();
  });
});
