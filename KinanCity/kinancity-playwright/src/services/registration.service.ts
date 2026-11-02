import { Page } from 'playwright';
import { AccountCredentials } from '../types';
import { CaptchaService } from './captcha.service';
import { logger } from '../core/logger.service';

export class RegistrationService {
  constructor(private captchaService: CaptchaService) {}

  /**
   * Fills registration fields across target forms using resilient selectors.
   */
  async fillRegistrationForm(page: Page, credentials: AccountCredentials): Promise<void> {
    logger.info('Populating registration form fields', { username: credentials.username });

    // Username
    const usernameInput = page.locator('input[name="username"], #id_username, input[autocomplete="username"]').first();
    await usernameInput.waitFor({ state: 'visible', timeout: 10000 });
    await usernameInput.fill(credentials.username);

    // Email & Confirm Email
    const emailInput = page.locator('input[name="email"], #id_email, input[type="email"]').first();
    await emailInput.fill(credentials.email);

    const confirmEmailInput = page.locator('input[name="confirm_email"], #id_confirm_email').first();
    if (await confirmEmailInput.isVisible().catch(() => false)) {
      await confirmEmailInput.fill(credentials.email);
    }

    // Password & Confirm Password
    if (credentials.password) {
      const passwordInput = page.locator('input[name="password"], #id_password, input[type="password"]').first();
      await passwordInput.fill(credentials.password);

      const confirmPasswordInput = page.locator('input[name="confirm_password"], #id_confirm_password').first();
      if (await confirmPasswordInput.isVisible().catch(() => false)) {
        await confirmPasswordInput.fill(credentials.password);
      }
    }

    // Accept terms checkbox if present
    const termsCheckbox = page.locator('input[type="checkbox"][name*="terms"], input[type="checkbox"][name*="agree"], #id_terms').first();
    if (await termsCheckbox.isVisible().catch(() => false)) {
      if (!(await termsCheckbox.isChecked())) {
        await termsCheckbox.check();
      }
    }
  }

  /**
   * Resolves security challenges (HITL or Sandbox) and clicks submit.
   */
  async submitForm(page: Page): Promise<boolean> {
    logger.info('Evaluating challenge before submission...');
    const challengeOutcome = await this.captchaService.handleChallenge(page);

    if (!challengeOutcome.success) {
      throw new Error(`Registration blocked by challenge: ${challengeOutcome.error}`);
    }

    logger.info('Submitting registration form...');
    const submitBtn = page.locator('button[type="submit"], input[type="submit"], #submit-btn').first();
    await submitBtn.waitFor({ state: 'visible', timeout: 5000 });
    await submitBtn.click();

    // Await response / network idle
    await page.waitForLoadState('networkidle').catch(() => {});
    return true;
  }
}
