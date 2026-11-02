import { Page } from 'playwright';
import { CaptchaType, ChallengeDetectionResult } from '../types';
import { logger } from '../core/logger.service';

export class CaptchaService {
  constructor(
    private operatorTimeoutMs: number = 120000,
    private pollIntervalMs: number = 1000,
    public isSandboxMode: boolean = false
  ) {}

  /**
   * Scans the active page and all child frames for security challenges and classifies them.
   */
  async detectChallenge(page: Page): Promise<ChallengeDetectionResult> {
    const frames = page.frames();

    // 1. Check frame URLs for known vendors
    for (const frame of frames) {
      const url = frame.url().toLowerCase();
      if (url.includes('recaptcha/api2') || url.includes('google.com/recaptcha')) {
        return {
          detected: true,
          type: CaptchaType.RECAPTCHA_V2,
          isActive: await this.isRecaptchaActive(page),
          frameUrl: frame.url(),
        };
      }
      if (url.includes('recaptcha/enterprise') || url.includes('recaptcha/api.js?render=')) {
        return {
          detected: true,
          type: CaptchaType.RECAPTCHA_V3,
          isActive: true,
          frameUrl: frame.url(),
        };
      }
      if (url.includes('hcaptcha.com')) {
        return {
          detected: true,
          type: CaptchaType.HCAPTCHA,
          isActive: await this.isHcaptchaActive(page),
          frameUrl: frame.url(),
        };
      }
      if (url.includes('cloudflare.com/cdn-cgi/challenge-platform') || url.includes('challenges.cloudflare.com')) {
        return {
          detected: true,
          type: CaptchaType.TURNSTILE,
          isActive: await this.isTurnstileActive(page),
          frameUrl: frame.url(),
        };
      }
    }

    // 2. Check DOM selectors on the main document
    const turnstileElement = await page.$('.cf-turnstile, #cf-turnstile, [data-sitekey][class*="turnstile"]');
    if (turnstileElement) {
      const isHidden = await turnstileElement.evaluate((el) => {
        const style = window.getComputedStyle(el);
        return style.display === 'none' || style.visibility === 'hidden';
      }).catch(() => false);

      if (!isHidden) {
        return {
          detected: true,
          type: CaptchaType.TURNSTILE,
          isActive: await this.isTurnstileActive(page),
        };
      }
    }

    const recaptchaElement = await page.$('.g-recaptcha, [data-sitekey][class*="recaptcha"]');
    if (recaptchaElement) {
      const isHidden = await recaptchaElement.evaluate((el) => {
        const style = window.getComputedStyle(el);
        return style.display === 'none' || style.visibility === 'hidden';
      }).catch(() => false);

      if (!isHidden) {
        return {
          detected: true,
          type: CaptchaType.RECAPTCHA_V2,
          isActive: await this.isRecaptchaActive(page),
        };
      }
    }

    const hcaptchaElement = await page.$('.h-captcha, [data-sitekey][class*="hcaptcha"]');
    if (hcaptchaElement) {
      const isHidden = await hcaptchaElement.evaluate((el) => {
        const style = window.getComputedStyle(el);
        return style.display === 'none' || style.visibility === 'hidden';
      }).catch(() => false);

      if (!isHidden) {
        return {
          detected: true,
          type: CaptchaType.HCAPTCHA,
          isActive: await this.isHcaptchaActive(page),
        };
      }
    }

    // Unknown challenge fallback (e.g. generic challenge container)
    const genericChallenge = await page.$('#challenge-running, #challenge-form, .challenge-container');
    if (genericChallenge) {
      const isHidden = await genericChallenge.evaluate((el) => {
        const style = window.getComputedStyle(el);
        return style.display === 'none' || style.visibility === 'hidden';
      }).catch(() => false);

      if (!isHidden) {
        return {
          detected: true,
          type: CaptchaType.UNKNOWN,
          isActive: true,
        };
      }
    }

    return {
      detected: false,
      type: CaptchaType.NONE,
      isActive: false,
    };
  }

  private async isRecaptchaActive(page: Page): Promise<boolean> {
    const token = await page.$eval(
      'textarea[name="g-recaptcha-response"], #g-recaptcha-response',
      (el) => (el as HTMLTextAreaElement).value
    ).catch(() => null);

    return !token || token.trim().length === 0;
  }

  private async isHcaptchaActive(page: Page): Promise<boolean> {
    const token = await page.$eval(
      'textarea[name="h-captcha-response"], [name="h-captcha-response"]',
      (el) => (el as HTMLTextAreaElement).value
    ).catch(() => null);

    return !token || token.trim().length === 0;
  }

  private async isTurnstileActive(page: Page): Promise<boolean> {
    const token = await page.$eval(
      'input[name="cf-turnstile-response"], [name="cf-turnstile-response"]',
      (el) => (el as HTMLInputElement).value
    ).catch(() => null);

    return !token || token.trim().length === 0;
  }

  /**
   * Confirms whether a challenge has been successfully verified by checking the presence of a non-empty response token.
   */
  async isVerificationComplete(page: Page, type: CaptchaType): Promise<boolean> {
    try {
      switch (type) {
        case CaptchaType.RECAPTCHA_V2:
          return !(await this.isRecaptchaActive(page));
        case CaptchaType.HCAPTCHA:
          return !(await this.isHcaptchaActive(page));
        case CaptchaType.TURNSTILE:
          return !(await this.isTurnstileActive(page));
        case CaptchaType.RECAPTCHA_V3:
        case CaptchaType.NONE:
          return true;
        case CaptchaType.UNKNOWN:
        default:
          return false;
      }
    } catch {
      return false;
    }
  }

  /**
   * Handles security challenges compliantly:
   * Pauses execution for Human-in-the-Loop (HITL) on interactive challenges.
   * Resumes when a verified response token is populated or submit button is unlocked.
   */
  async handleChallenge(page: Page): Promise<{ success: boolean; type: CaptchaType; error?: string }> {
    const challenge = await this.detectChallenge(page);

    if (!challenge.detected || !challenge.isActive) {
      logger.info('No active security challenge requires human verification', { challenge });
      return { success: true, type: challenge.type };
    }

    // ── Sandbox Mode / Automated Test Key Fulfillment ────────────────────────
    if (this.isSandboxMode) {
      logger.info(`[Sandbox] Automatically fulfilling challenge [${challenge.type}] using test credentials...`);
      const hasSandboxBtn = await page.$('#sandbox-solve-btn');
      if (hasSandboxBtn) {
        await hasSandboxBtn.click();
      } else {
        await page.evaluate((type) => {
          if (type === 'reCAPTCHA_v2') {
            const el = (document.getElementById('g-recaptcha-response') || document.querySelector('textarea[name="g-recaptcha-response"]')) as HTMLTextAreaElement;
            if (el) el.value = 'SANDBOX_TOKEN_PASSED';
          } else if (type === 'Cloudflare_Turnstile') {
            const el = document.querySelector('input[name="cf-turnstile-response"]') as HTMLInputElement;
            if (el) el.value = 'XXXX.DUMMY.TOKEN.XXXX';
          } else if (type === 'hCaptcha') {
            const el = document.querySelector('textarea[name="h-captcha-response"]') as HTMLTextAreaElement;
            if (el) el.value = '10000000-aaaa-bbbb-cccc-000000000001';
          }
        }, challenge.type as string);
      }

      const verified = await this.isVerificationComplete(page, challenge.type);
      if (verified) {
        logger.info(`[Sandbox] Challenge [${challenge.type}] successfully verified via sandbox token.`);
        return { success: true, type: challenge.type };
      }
    }

    logger.warn(`Security Challenge Detected: [${challenge.type}]. Pausing for Human-in-the-Loop (HITL)...`);
    const startTime = Date.now();

    while (Date.now() - startTime < this.operatorTimeoutMs) {
      const isComplete = await this.isVerificationComplete(page, challenge.type);
      if (isComplete) {
        logger.info(`Security Challenge [${challenge.type}] verified successfully by operator.`);
        return { success: true, type: challenge.type };
      }
      await page.waitForTimeout(this.pollIntervalMs);
    }

    logger.error('Human verification timed out', {
      type: challenge.type,
      timeoutMs: this.operatorTimeoutMs,
    });
    return {
      success: false,
      type: challenge.type,
      error: `Operator verification timed out after ${this.operatorTimeoutMs / 1000}s`,
    };
  }
}
