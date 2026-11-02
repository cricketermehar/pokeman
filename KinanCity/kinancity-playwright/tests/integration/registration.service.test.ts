import { test, expect } from '@playwright/test';
import { startTestApp, TestAppServer } from '../../fixtures/test-app/server';
import { BrowserService } from '../../src/core/browser.service';
import { CaptchaService } from '../../src/services/captcha.service';
import { RegistrationService } from '../../src/services/registration.service';
import { loadConfig } from '../../src/config/environment';

test.describe('Registration Service Integration', () => {
  let server: TestAppServer;
  let browserService: BrowserService;
  let captchaService: CaptchaService;
  let registrationService: RegistrationService;
  const testPort = 3001;

  test.beforeAll(async () => {
    server = await startTestApp(testPort);
    const config = loadConfig({
      TEST_TARGET_URL: `http://localhost:${testPort}/signup`,
      ALLOWED_ORIGINS: `http://localhost:${testPort}`,
      TEST_ACCOUNT_USERNAME: 'PtcTester99',
      TEST_ACCOUNT_EMAIL: 'ptc_tester@example.com',
      HEADLESS: 'true',
    });

    browserService = new BrowserService(config);
    await browserService.initialize();
    captchaService = new CaptchaService(5000);
    registrationService = new RegistrationService(captchaService);
  });

  test.afterAll(async () => {
    if (browserService) {
      await browserService.teardown();
    }
    if (server) {
      await server.close();
    }
  });

  test('fills registration form and submits successfully with sandbox challenge verification', async () => {
    const context = await browserService.createContext('reg_test');
    const page = await context.newPage();

    await page.goto(`http://localhost:${testPort}/signup`, { waitUntil: 'domcontentloaded' });

    await registrationService.fillRegistrationForm(page, {
      username: 'PtcTester99',
      email: 'ptc_tester@example.com',
      password: 'SafePassword123!',
    });

    // Simulate sandbox verification button click
    await page.click('#sandbox-solve-btn');
    const tokenVal = await page.locator('#g-recaptcha-response').inputValue();
    expect(tokenVal).toBe('SANDBOX_TOKEN_PASSED');

    const submitted = await registrationService.submitForm(page);
    expect(submitted).toBe(true);

    // Verify submission response text
    const confirmationText = await page.textContent('#confirmation-msg');
    expect(confirmationText).toContain('Welcome PtcTester99');
    expect(confirmationText).toContain('ptc_tester@example.com');

    await browserService.closeContext(context);
  });
});
