import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import { SessionManager } from '../../src/core/session.manager';

test.describe('Session Manager Security and Validation', () => {
  const testSessionName = 'test_unit_session';

  test.afterEach(() => {
    SessionManager.invalidateSession(testSessionName);
  });

  test('sanitizes session names and prevents path traversal', () => {
    expect(SessionManager.sanitizeSessionName('normal_user')).toBe('normal_user');
    expect(SessionManager.sanitizeSessionName('../../etc/passwd')).toBe('______etc_passwd');
    expect(() => SessionManager.sanitizeSessionName('')).toThrow();
  });

  test('validates authentic storage state JSON structure', () => {
    const filePath = SessionManager.getSessionPath(testSessionName);
    const validPayload = {
      cookies: [
        {
          name: 'session_token',
          value: 'abc123xyz',
          domain: 'example.com',
          path: '/',
          expires: Math.floor(Date.now() / 1000) + 3600,
        },
      ],
      origins: [],
    };

    fs.writeFileSync(filePath, JSON.stringify(validPayload));
    const result = SessionManager.validateSessionFile(filePath);
    expect(result.isValid).toBe(true);
  });

  test('detects expired session cookies', () => {
    const filePath = SessionManager.getSessionPath(testSessionName);
    const expiredPayload = {
      cookies: [
        {
          name: 'session_token',
          value: 'abc123xyz',
          domain: 'example.com',
          path: '/',
          expires: Math.floor(Date.now() / 1000) - 3600, // expired 1h ago
        },
      ],
      origins: [],
    };

    fs.writeFileSync(filePath, JSON.stringify(expiredPayload));
    const result = SessionManager.validateSessionFile(filePath);
    expect(result.isValid).toBe(false);
    expect(result.reason).toContain('expired');
  });

  test('handles corrupted session JSON gracefully without crashing', () => {
    const filePath = SessionManager.getSessionPath(testSessionName);
    fs.writeFileSync(filePath, '{ bad_json: corrupt content ...');

    const result = SessionManager.validateSessionFile(filePath);
    expect(result.isValid).toBe(false);
    expect(result.reason).toContain('Corrupted');

    // hasValidSession should clean up corrupted session
    expect(SessionManager.hasValidSession(testSessionName)).toBe(false);
    expect(fs.existsSync(filePath)).toBe(false);
  });
});
