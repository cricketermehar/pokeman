import { test, expect } from '@playwright/test';
import { loadConfig } from '../../src/config/environment';

test.describe('Environment Configuration Validation', () => {
  const baseValid = {
    APP_ENV: 'testing',
    TEST_TARGET_URL: 'http://localhost:3000/signup',
    ALLOWED_ORIGINS: 'http://localhost:3000,http://127.0.0.1:3000',
    ALLOW_PRODUCTION_REGISTRATION: 'false',
    TEST_ACCOUNT_USERNAME: 'ValidTrainer01',
    TEST_ACCOUNT_PASSWORD: 'ValidPassword123!',
    TEST_ACCOUNT_EMAIL: 'trainer@example.com',
  };

  test('loads valid environment configuration cleanly', () => {
    const config = loadConfig(baseValid);
    expect(config.TEST_ACCOUNT_USERNAME).toBe('ValidTrainer01');
    expect(config.APP_ENV).toBe('testing');
    expect(config.HEADLESS).toBe(true);
    expect(config.MAX_RETRIES).toBe(3);
  });

  test('rejects username shorter than 6 characters', () => {
    expect(() => {
      loadConfig({ ...baseValid, TEST_ACCOUNT_USERNAME: 'abc' });
    }).toThrow(/at least 6 characters/i);
  });

  test('rejects username with non-alphanumeric characters', () => {
    expect(() => {
      loadConfig({ ...baseValid, TEST_ACCOUNT_USERNAME: 'bad_user!' });
    }).toThrow(/alphanumeric/i);
  });

  test('redacts password from validation error outputs', () => {
    try {
      loadConfig({ ...baseValid, TEST_ACCOUNT_PASSWORD: 'short' });
      expect(true).toBe(false); // Should not reach
    } catch (err: any) {
      expect(err.message).not.toContain('short');
      expect(err.message).toContain('details omitted for security');
    }
  });

  test('rejects target URL origin not in ALLOWED_ORIGINS', () => {
    expect(() => {
      loadConfig({
        ...baseValid,
        TEST_TARGET_URL: 'http://unauthorized-domain.com/signup',
      });
    }).toThrow(/not in ALLOWED_ORIGINS/i);
  });

  test('rejects external production URL if ALLOW_PRODUCTION_REGISTRATION is false', () => {
    expect(() => {
      loadConfig({
        ...baseValid,
        TEST_TARGET_URL: 'https://trainer.pokemon.com/en-us/profile/signup',
        ALLOWED_ORIGINS: 'http://localhost:3000,https://trainer.pokemon.com',
        ALLOW_PRODUCTION_REGISTRATION: 'false',
      });
    }).toThrow(/Refusing execution against non-local origin/i);
  });

  test('accepts external URL if ALLOW_PRODUCTION_REGISTRATION is true and origin is allowed', () => {
    const config = loadConfig({
      ...baseValid,
      TEST_TARGET_URL: 'https://trainer.pokemon.com/en-us/profile/signup',
      ALLOWED_ORIGINS: 'http://localhost:3000,https://trainer.pokemon.com',
      ALLOW_PRODUCTION_REGISTRATION: 'true',
    });
    expect(config.ALLOW_PRODUCTION_REGISTRATION).toBe(true);
  });
});
