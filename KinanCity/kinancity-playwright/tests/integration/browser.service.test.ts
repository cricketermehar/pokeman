import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import { BrowserService } from '../../src/core/browser.service';
import { loadConfig } from '../../src/config/environment';

test.describe('Browser Service Lifecycle & Diagnostics', () => {
  let browserService: BrowserService;

  test.beforeAll(() => {
    const config = loadConfig({
      TEST_TARGET_URL: 'http://localhost:3000/signup',
      ALLOWED_ORIGINS: 'http://localhost:3000',
      TEST_ACCOUNT_USERNAME: 'TestTrainer99',
      TEST_ACCOUNT_EMAIL: 'test@example.com',
      HEADLESS: 'true',
    });
    browserService = new BrowserService(config);
  });

  test.afterAll(async () => {
    await browserService.teardown();
  });

  test('initializes browser and spawns isolated contexts', async () => {
    const context1 = await browserService.createContext('session1');
    const context2 = await browserService.createContext('session2');

    expect(context1).not.toBe(context2);

    const page1 = await context1.newPage();
    await page1.setContent('<html><body><h1>Page 1</h1></body></html>');
    expect(await page1.textContent('h1')).toBe('Page 1');

    await browserService.closeContext(context1);
    await browserService.closeContext(context2);
  });

  test('captures diagnostic screenshot to disk safely', async () => {
    const context = await browserService.createContext();
    const page = await context.newPage();
    await page.setContent('<html><body style="background: red;"><h1>Failure State</h1></body></html>');

    const screenshotPath = await browserService.captureScreenshot(page, 'test_diagnostic_failure');
    expect(fs.existsSync(screenshotPath)).toBe(true);

    // Clean up test screenshot
    try {
      fs.unlinkSync(screenshotPath);
    } catch {}

    await browserService.closeContext(context);
  });
});
