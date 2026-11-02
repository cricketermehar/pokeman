import { test, expect } from '@playwright/test';
import { RetryManager, PermanentError, TransientError } from '../../src/core/retry.manager';

test.describe('Retry and Recovery Manager', () => {
  test('correctly classifies transient vs permanent errors', () => {
    const manager = new RetryManager();

    expect(manager.isTransient(new Error('ETIMEDOUT: Connection timed out'))).toBe(true);
    expect(manager.isTransient(new Error('503 Service Unavailable'))).toBe(true);
    expect(manager.isTransient(new Error('429 Too Many Requests (Rate limit)'))).toBe(true);
    expect(manager.isTransient(new TransientError('Custom transient error'))).toBe(true);

    expect(manager.isTransient(new Error('Validation error: Invalid username'))).toBe(false);
    expect(manager.isTransient(new Error('400 Bad Request'))).toBe(false);
    expect(manager.isTransient(new Error('403 Forbidden'))).toBe(false);
    expect(manager.isTransient(new Error('Username already exists'))).toBe(false);
    expect(manager.isTransient(new PermanentError('Custom permanent error'))).toBe(false);
  });

  test('exponential backoff calculates increasing delays with jitter', () => {
    const manager = new RetryManager({ baseDelayMs: 100, maxDelayMs: 2000, jitterFactor: 0.1 });
    const delay1 = manager.calculateDelay(1);
    const delay2 = manager.calculateDelay(2);
    const delay3 = manager.calculateDelay(3);

    expect(delay1).toBeGreaterThanOrEqual(80);
    expect(delay1).toBeLessThanOrEqual(120);

    expect(delay2).toBeGreaterThanOrEqual(170);
    expect(delay2).toBeLessThanOrEqual(230);

    expect(delay3).toBeGreaterThan(delay2);
  });

  test('retries transient errors and succeeds upon recovery', async () => {
    const manager = new RetryManager({ maxRetries: 3, baseDelayMs: 20 });
    let attempts = 0;

    const result = await manager.execute(async () => {
      attempts++;
      if (attempts < 3) {
        throw new Error('ETIMEDOUT: temporary network blip');
      }
      return 'SUCCESS_DATA';
    }, 'test-network-call');

    expect(result).toBe('SUCCESS_DATA');
    expect(attempts).toBe(3);
  });

  test('never retries permanent errors', async () => {
    const manager = new RetryManager({ maxRetries: 3, baseDelayMs: 20 });
    let attempts = 0;

    await expect(
      manager.execute(async () => {
        attempts++;
        throw new Error('400 Bad Request: Account already exists');
      }, 'test-duplicate-check')
    ).rejects.toThrow(/already exists/i);

    expect(attempts).toBe(1);
  });

  test('protects non-idempotent operations from blind re-execution', async () => {
    const manager = new RetryManager({ maxRetries: 3, baseDelayMs: 20 });
    let attempts = 0;

    await expect(
      manager.execute(
        async () => {
          attempts++;
          throw new Error('500 Internal Error during submission');
        },
        'form-submission',
        { isIdempotent: false }
      )
    ).rejects.toThrow();

    expect(attempts).toBe(1);
  });
});
