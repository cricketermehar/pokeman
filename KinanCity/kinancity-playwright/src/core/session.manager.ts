import * as fs from 'fs';
import * as path from 'path';
import { BrowserContext } from 'playwright';
import { z } from 'zod';
import { logger } from './logger.service';

const CookieSchema = z.object({
  name: z.string(),
  value: z.string(),
  domain: z.string(),
  path: z.string(),
  expires: z.number().optional(),
  httpOnly: z.boolean().optional(),
  secure: z.boolean().optional(),
  sameSite: z.enum(['Strict', 'Lax', 'None']).optional(),
});

const OriginStateSchema = z.object({
  origin: z.string(),
  localStorage: z.array(z.object({ name: z.string(), value: z.string() })),
});

export const StorageStateSchema = z.object({
  cookies: z.array(CookieSchema),
  origins: z.array(OriginStateSchema).optional().default([]),
});

export type ValidatedStorageState = z.infer<typeof StorageStateSchema>;

export class SessionManager {
  private static readonly SESSION_DIR = path.resolve('sessions');

  /**
   * Sanitizes session name to prevent path traversal attacks.
   */
  public static sanitizeSessionName(name: string): string {
    const sanitized = name.replace(/[^a-zA-Z0-9_-]/g, '_');
    if (!sanitized || sanitized === '_') {
      throw new Error(`Invalid session identifier: '${name}'`);
    }
    return sanitized;
  }

  public static getSessionPath(sessionName: string): string {
    const cleanName = this.sanitizeSessionName(sessionName);
    this.ensureDirectoryExists();
    return path.join(this.SESSION_DIR, `${cleanName}_storage_state.json`);
  }

  private static ensureDirectoryExists(): void {
    if (!fs.existsSync(this.SESSION_DIR)) {
      fs.mkdirSync(this.SESSION_DIR, { recursive: true, mode: 0o700 });
    }
  }

  /**
   * Validates stored session JSON structure and checks for cookie expiration.
   */
  public static validateSessionFile(filePath: string): { isValid: boolean; reason?: string } {
    if (!fs.existsSync(filePath)) {
      return { isValid: false, reason: 'File does not exist' };
    }

    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const parsed = JSON.parse(content);
      const validation = StorageStateSchema.safeParse(parsed);

      if (!validation.success) {
        return { isValid: false, reason: 'Malformed storage state schema' };
      }

      // Check if primary session cookies have expired
      const nowSeconds = Math.floor(Date.now() / 1000);
      const activeCookies = validation.data.cookies.filter(
        (c) => c.expires === undefined || c.expires === -1 || c.expires > nowSeconds
      );

      if (activeCookies.length === 0 && validation.data.cookies.length > 0) {
        return { isValid: false, reason: 'All session cookies have expired' };
      }

      return { isValid: true };
    } catch (err) {
      return { isValid: false, reason: `Corrupted JSON session file: ${err}` };
    }
  }

  /**
   * Checks if a valid, uncorrupted, and unexpired session exists for the given name.
   */
  public static hasValidSession(sessionName: string): boolean {
    try {
      const file = this.getSessionPath(sessionName);
      const check = this.validateSessionFile(file);
      if (!check.isValid && fs.existsSync(file)) {
        logger.warn('Session file is invalid or expired. Removing.', { sessionName, reason: check.reason });
        this.invalidateSession(sessionName);
      }
      return check.isValid;
    } catch {
      return false;
    }
  }

  /**
   * Persists browser session state with restrictive filesystem permissions (0o600).
   */
  public static async persistSession(context: BrowserContext, sessionName: string): Promise<string> {
    const file = this.getSessionPath(sessionName);
    await context.storageState({ path: file });

    // Enforce restrictive file permissions (read/write by owner only) on Unix
    try {
      fs.chmodSync(file, 0o600);
    } catch {
      // Graceful fallback on filesystems that don't support chmod
    }

    logger.info('Session state securely persisted', { sessionName });
    return file;
  }

  /**
   * Safely invalidates/deletes a session file.
   */
  public static invalidateSession(sessionName: string): void {
    try {
      const file = this.getSessionPath(sessionName);
      if (fs.existsSync(file)) {
        fs.unlinkSync(file);
        logger.info('Session state invalidated', { sessionName });
      }
    } catch (err) {
      logger.warn('Failed invalidating session file', { sessionName, error: String(err) });
    }
  }
}
