import { MailboxAdapter, MailboxQueryOptions } from './mailbox.adapter';
import { VerificationMessage } from '../types';
import { logger } from '../core/logger.service';

export class MockMailboxAdapter implements MailboxAdapter {
  readonly adapterName = 'MockMailboxAdapter';
  private queuedMessages: VerificationMessage[] = [];
  private lastProcessedToken?: string;

  constructor(private testServerUrl?: string) {}

  /**
   * Pushes a simulated incoming email into the mock mailbox.
   */
  public pushMessage(message: VerificationMessage): void {
    this.queuedMessages.push(message);
    logger.debug('[MockMailbox] Queued simulated message', {
      sender: message.sender,
      recipient: message.recipient,
      subject: message.subject,
    });
  }

  public clear(): void {
    this.queuedMessages = [];
  }

  async fetchVerificationMessage(options: MailboxQueryOptions): Promise<VerificationMessage | null> {
    const startTime = Date.now();
    const pollInterval = 200;

    while (Date.now() - startTime < options.timeoutMs) {
      // Find the latest message that matches recipient, sender, and was sent after sinceTimestamp
      const matchIndex = this.queuedMessages.findIndex(
        (m) =>
          m.recipient.toLowerCase() === options.recipient.toLowerCase() &&
          m.sender.toLowerCase().includes(options.expectedSender.toLowerCase()) &&
          m.timestamp >= options.sinceTimestamp
      );

      if (matchIndex !== -1) {
        const [matched] = this.queuedMessages.splice(matchIndex, 1);
        logger.info('[MockMailbox] Found matching verification message', {
          recipient: matched.recipient,
          sender: matched.sender,
        });
        return matched;
      }

      // Check test server API endpoint if configured
      if (this.testServerUrl) {
        try {
          const res = await fetch(`${this.testServerUrl}/api/last-token`);
          if (res.ok) {
            const data: any = await res.json();
            if (data?.token && data.token !== this.lastProcessedToken) {
              this.lastProcessedToken = data.token;
              logger.info('[MockMailbox] Captured mock activation token from test server', {
                recipient: options.recipient,
              });
              return {
                id: `msg-${Date.now()}`,
                sender: 'noreply@pokemon.com',
                recipient: options.recipient,
                subject: 'Activate Your Pokémon Trainer Club Account',
                activationUrl: `${this.testServerUrl}/profile/activated/${data.token}`,
                timestamp: Date.now(),
              };
            }
          }
        } catch {}
      }

      await new Promise((res) => setTimeout(res, pollInterval));
    }

    return null;
  }
}
