import { BrowserContext } from 'playwright';
import { MailboxAdapter } from '../adapters/mailbox.adapter';
import { VerificationMessage } from '../types';
import { Environment } from '../config/environment';
import { logger } from '../core/logger.service';

export class EmailVerificationService {
  constructor(
    private adapter: MailboxAdapter,
    private config: Environment
  ) {}

  /**
   * Safely extracts and validates the activation URL from a verification message.
   * Enforces origin allowlist validation to protect against malicious redirects or phishing.
   */
  public extractAndValidateActivationUrl(message: VerificationMessage): string {
    const rawUrl = message.activationUrl || this.findUrlInBody(message.rawBody || '');

    if (!rawUrl) {
      throw new Error(`No activation URL could be extracted from verification message (ID: ${message.id})`);
    }

    let parsedUrl: URL;
    try {
      parsedUrl = new URL(rawUrl);
    } catch {
      throw new Error(`Extracted activation link is not a valid URL: ${rawUrl}`);
    }

    const isOriginAllowed = this.config.ALLOWED_ORIGINS.some((allowed) => {
      try {
        return new URL(allowed).origin === parsedUrl.origin;
      } catch {
        return false;
      }
    });

    if (!isOriginAllowed) {
      throw new Error(
        `Security Violation: Activation URL origin '${parsedUrl.origin}' is not in configured ALLOWED_ORIGINS`
      );
    }

    // Mask the token in log output
    const sanitizedLogUrl = rawUrl.replace(/(activated\/)[a-zA-Z0-9_-]+/gi, '$1[TOKEN_REDACTED]');
    logger.info('Activation link validated against allowlist', { url: sanitizedLogUrl });

    return rawUrl;
  }

  private findUrlInBody(body: string): string | null {
    // Matches modern PTC activation patterns
    const match = body.match(/https?:\/\/[^\s"']+(?:\/activated\/|\/verify\/)[a-zA-Z0-9_\-]+/i);
    return match ? match[0] : null;
  }

  /**
   * Waits for verification email arriving after workflowStartTime.
   */
  async waitForVerificationToken(
    workflowStartTime: number,
    context?: BrowserContext
  ): Promise<string> {
    logger.info('Awaiting verification email dispatch...', {
      recipient: this.config.TEST_ACCOUNT_EMAIL,
      adapter: this.adapter.adapterName,
    });

    const message = await this.adapter.fetchVerificationMessage(
      {
        recipient: this.config.TEST_ACCOUNT_EMAIL,
        expectedSender: 'pokemon',
        sinceTimestamp: workflowStartTime,
        timeoutMs: this.config.OPERATOR_TIMEOUT_MS,
      },
      context
    );

    if (!message) {
      throw new Error(
        `Email verification message did not arrive within timeout (${this.config.OPERATOR_TIMEOUT_MS / 1000}s)`
      );
    }

    return this.extractAndValidateActivationUrl(message);
  }
}
