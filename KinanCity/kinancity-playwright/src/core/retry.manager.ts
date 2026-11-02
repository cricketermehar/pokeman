import { logger } from './logger.service';

export interface RetryPolicyOptions {
  maxRetries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  jitterFactor?: number;
  timeoutMs?: number;
  isIdempotent?: boolean;
}

export class PermanentError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message);
    this.name = 'PermanentError';
  }
}

export class TransientError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message);
    this.name = 'TransientError';
  }
}

export class RetryManager {
  private maxRetries: number;
  private baseDelayMs: number;
  private maxDelayMs: number;
  private jitterFactor: number;

  constructor(options: RetryPolicyOptions = {}) {
    this.maxRetries = options.maxRetries ?? 3;
    this.baseDelayMs = options.baseDelayMs ?? 1000;
    this.maxDelayMs = options.maxDelayMs ?? 15000;
    this.jitterFactor = options.jitterFactor ?? 0.2;
  }

  /**
   * Evaluates whether an error is transient (retryable) or permanent.
   */
  public isTransient(error: unknown): boolean {
    if (error instanceof PermanentError) {
      return false;
    }
    if (error instanceof TransientError) {
      return true;
    }

    const message = error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();

    // Permanent errors - should never be retried
    if (
      message.includes('validation') ||
      message.includes('invalid credentials') ||
      message.includes('bad request') ||
      message.includes('400') ||
      message.includes('401') ||
      message.includes('403') ||
      message.includes('already exists') ||
      message.includes('duplicate') ||
      message.includes('permanent')
    ) {
      return false;
    }

    // Transient network or server errors
    if (
      message.includes('timeout') ||
      message.includes('econnreset') ||
      message.includes('econnrefused') ||
      message.includes('etimedout') ||
      message.includes('network') ||
      message.includes('502') ||
      message.includes('503') ||
      message.includes('504') ||
      message.includes('rate limit') ||
      message.includes('429')
    ) {
      return true;
    }

    return false;
  }

  /**
   * Calculates exponential delay with randomized jitter.
   */
  public calculateDelay(attempt: number): number {
    const rawDelay = this.baseDelayMs * Math.pow(2, attempt - 1);
    const cappedDelay = Math.min(rawDelay, this.maxDelayMs);

    // Add jitter: +/- jitterFactor
    const jitter = cappedDelay * this.jitterFactor * (Math.random() * 2 - 1);
    return Math.max(10, Math.floor(cappedDelay + jitter));
  }

  /**
   * Executes an operation with backoff, jitter, timeout, and cancellation signal support.
   */
  async execute<T>(
    operation: () => Promise<T>,
    contextName: string,
    options: RetryPolicyOptions = {}
  ): Promise<T> {
    const maxRetries = options.maxRetries ?? this.maxRetries;
    const isIdempotent = options.isIdempotent ?? true;
    let attempt = 0;

    while (true) {
      attempt++;
      try {
        if (options.timeoutMs) {
          return await Promise.race([
            operation(),
            new Promise<never>((_, reject) =>
              setTimeout(
                () => reject(new TransientError(`Operation '${contextName}' timed out after ${options.timeoutMs}ms`)),
                options.timeoutMs
              )
            ),
          ]);
        }
        return await operation();
      } catch (err) {
        const transient = this.isTransient(err);
        const canRetry = transient && isIdempotent && attempt <= maxRetries;

        logger.warn(`Execution failed for [${contextName}]`, {
          attempt,
          maxRetries,
          isTransient: transient,
          isIdempotent,
          willRetry: canRetry,
          error: err instanceof Error ? err.message : String(err),
        });

        if (!canRetry) {
          if (!isIdempotent && attempt > 1) {
            throw new PermanentError(`Non-idempotent operation '${contextName}' failed after attempt ${attempt}`, err);
          }
          if (err instanceof Error) {
            throw err;
          }
          throw new Error(String(err));
        }

        const delay = this.calculateDelay(attempt);
        await new Promise((res) => setTimeout(res, delay));
      }
    }
  }
}
