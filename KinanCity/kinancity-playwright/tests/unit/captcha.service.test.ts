import { test, expect } from '@playwright/test';
import { CaptchaService } from '../../src/services/captcha.service';
import { CaptchaType } from '../../src/types';

test.describe('CAPTCHA Detection and Classification Service', () => {
  let captchaService: CaptchaService;

  test.beforeEach(() => {
    captchaService = new CaptchaService(2000, 200); // 2s timeout for fast unit tests
  });

  test('reports NONE when page has no challenge widgets', async ({ page }) => {
    await page.setContent('<html><body><form><input name="username"/><button>Submit</button></form></body></html>');
    const result = await captchaService.detectChallenge(page);
    expect(result.detected).toBe(false);
    expect(result.type).toBe(CaptchaType.NONE);
    expect(result.isActive).toBe(false);
  });

  test('detects and distinguishes active vs completed reCAPTCHA v2', async ({ page }) => {
    // 1. Inactive / uncompleted state (empty textarea)
    await page.setContent(`
      <html><body>
        <div class="g-recaptcha" data-sitekey="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"></div>
        <textarea name="g-recaptcha-response" id="g-recaptcha-response"></textarea>
      </body></html>
    `);

    let result = await captchaService.detectChallenge(page);
    expect(result.detected).toBe(true);
    expect(result.type).toBe(CaptchaType.RECAPTCHA_V2);
    expect(result.isActive).toBe(true);

    // 2. Simulated operator verification (token populated)
    await page.fill('#g-recaptcha-response', '03AFcWeA_simulated_valid_token_xyz');
    result = await captchaService.detectChallenge(page);
    expect(result.isActive).toBe(false);
    expect(await captchaService.isVerificationComplete(page, CaptchaType.RECAPTCHA_V2)).toBe(true);
  });

  test('detects Cloudflare Turnstile challenge and token fulfillment', async ({ page }) => {
    await page.setContent(`
      <html><body>
        <div class="cf-turnstile" data-sitekey="1x00000000000000000000AA"></div>
        <input type="hidden" name="cf-turnstile-response" id="cf-turnstile-response" value=""/>
      </body></html>
    `);

    let result = await captchaService.detectChallenge(page);
    expect(result.detected).toBe(true);
    expect(result.type).toBe(CaptchaType.TURNSTILE);
    expect(result.isActive).toBe(true);

    // Simulate completion
    await page.$eval('#cf-turnstile-response', (el) => ((el as HTMLInputElement).value = 'turnstile_token_123'));
    expect(await captchaService.isVerificationComplete(page, CaptchaType.TURNSTILE)).toBe(true);
  });

  test('times out gracefully when human verification is not completed', async ({ page }) => {
    await page.setContent(`
      <html><body>
        <div class="g-recaptcha"></div>
        <textarea name="g-recaptcha-response"></textarea>
      </body></html>
    `);

    const outcome = await captchaService.handleChallenge(page);
    expect(outcome.success).toBe(false);
    expect(outcome.error).toContain('timed out');
  });
});
