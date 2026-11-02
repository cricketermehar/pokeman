import { test, expect } from '@playwright/test';
import { EmailVerificationService } from '../../src/services/email.service';
import { MockMailboxAdapter } from '../../src/adapters/mock-mailbox.adapter';
import { loadConfig } from '../../src/config/environment';

test.describe('Email Verification Service', () => {
  let mockMailbox: MockMailboxAdapter;
  let emailService: EmailVerificationService;
  const config = loadConfig({
    TEST_TARGET_URL: 'http://localhost:3000/signup',
    ALLOWED_ORIGINS: 'http://localhost:3000,https://trainer.pokemon.com',
    TEST_ACCOUNT_USERNAME: 'TrainerTest01',
    TEST_ACCOUNT_EMAIL: 'Counterass100@proton.me',
  });

  test.beforeEach(() => {
    mockMailbox = new MockMailboxAdapter();
    emailService = new EmailVerificationService(mockMailbox, config);
  });

  test('extracts and validates activation URL when origin is in allowlist', () => {
    const validMessage = {
      id: 'msg-01',
      sender: 'noreply@pokemon.com',
      recipient: 'Counterass100@proton.me',
      subject: 'Pokemon Trainer Club Activation',
      timestamp: Date.now(),
      activationUrl: 'https://trainer.pokemon.com/profile/activated/abc123token',
    };

    const extracted = emailService.extractAndValidateActivationUrl(validMessage);
    expect(extracted).toBe('https://trainer.pokemon.com/profile/activated/abc123token');
  });

  test('rejects activation URL when origin is NOT in allowlist (SSRF / Phishing defense)', () => {
    const maliciousMessage = {
      id: 'msg-malicious',
      sender: 'phishing@attacker.com',
      recipient: 'Counterass100@proton.me',
      subject: 'Fake Activation',
      timestamp: Date.now(),
      activationUrl: 'http://evil-phishing-domain.com/activated/steal-token',
    };

    expect(() => {
      emailService.extractAndValidateActivationUrl(maliciousMessage);
    }).toThrow(/Security Violation: Activation URL origin/i);
  });

  test('extracts URL from raw message body regex fallback', () => {
    const messageWithBody = {
      id: 'msg-body',
      sender: 'noreply@pokemon.com',
      recipient: 'Counterass100@proton.me',
      subject: 'Activate your account',
      timestamp: Date.now(),
      rawBody: 'Hello! Please click: https://trainer.pokemon.com/profile/activated/bodyToken99 to activate.',
    };

    const extracted = emailService.extractAndValidateActivationUrl(messageWithBody);
    expect(extracted).toBe('https://trainer.pokemon.com/profile/activated/bodyToken99');
  });

  test('discards stale verification messages arriving before workflow start', async () => {
    const workflowStartTime = Date.now();

    // Push stale message from 10 seconds ago
    mockMailbox.pushMessage({
      id: 'msg-stale',
      sender: 'noreply@pokemon.com',
      recipient: 'Counterass100@proton.me',
      subject: 'Old activation',
      timestamp: workflowStartTime - 10000,
      activationUrl: 'https://trainer.pokemon.com/profile/activated/stale123',
    });

    // Custom short timeout for test
    const shortTimeoutConfig = { ...config, OPERATOR_TIMEOUT_MS: 500 };
    const shortService = new EmailVerificationService(mockMailbox, shortTimeoutConfig);

    await expect(shortService.waitForVerificationToken(workflowStartTime)).rejects.toThrow(/did not arrive within timeout/i);
  });
});
