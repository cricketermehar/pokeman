import { test, expect } from '@playwright/test';
import { sanitizeData } from '../../src/core/logger.service';

test.describe('Logger Service Sensitive Data Sanitization', () => {
  test('redacts simple password strings in text', () => {
    const input = 'Logging user with password=SuperSecretPassword123! in query';
    const output = sanitizeData(input);
    expect(output).not.toContain('SuperSecretPassword123!');
    expect(output).toContain('password=[REDACTED]');
  });

  test('redacts activation URL token parameters', () => {
    const input = 'Target activation link: https://trainer.pokemon.com/profile/activated/abc-123-secret-token';
    const output = sanitizeData(input);
    expect(output).not.toContain('abc-123-secret-token');
    expect(output).toContain('activated/[TOKEN_REDACTED]');
  });

  test('recursively redacts nested object properties', () => {
    const payload = {
      user: 'Trainer01',
      auth: {
        password: 'TopSecretPassword',
        nested: {
          token: 'bearer-jwt-12345',
          cookie: 'session_id=abcdef',
          safeField: 'normalValue',
        },
      },
      tags: ['test', 'password=inlineSecret123'],
    };

    const sanitized = sanitizeData(payload);

    expect(sanitized.user).toBe('Trainer01');
    expect(sanitized.auth.password).toBe('[REDACTED]');
    expect(sanitized.auth.nested.token).toBe('[REDACTED]');
    expect(sanitized.auth.nested.cookie).toBe('[REDACTED]');
    expect(sanitized.auth.nested.safeField).toBe('normalValue');
    expect(sanitized.tags[1]).toContain('password=[REDACTED]');
    expect(sanitized.tags[1]).not.toContain('inlineSecret123');
  });
});
