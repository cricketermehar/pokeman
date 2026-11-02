import { BrowserContext } from 'playwright';
import { VerificationMessage } from '../types';

export interface MailboxQueryOptions {
  recipient: string;
  expectedSender: string;
  sinceTimestamp: number;
  timeoutMs: number;
}

export interface MailboxAdapter {
  readonly adapterName: string;

  /**
   * Polls the mailbox for the latest verification message meeting criteria.
   */
  fetchVerificationMessage(
    options: MailboxQueryOptions,
    context?: BrowserContext
  ): Promise<VerificationMessage | null>;

  /**
   * Closes or cleans up any adapter resources.
   */
  teardown?(): Promise<void>;
}
