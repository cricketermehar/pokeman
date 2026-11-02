import * as dotenv from 'dotenv';
import * as path from 'path';
import { z } from 'zod';

// Load .env relative to project root or current working dir
dotenv.config();

export const AppEnvSchema = z.enum(['development', 'testing', 'production']);
export type AppEnv = z.infer<typeof AppEnvSchema>;

export const RawEnvironmentSchema = z.object({
  APP_ENV: AppEnvSchema.default('testing'),
  TEST_TARGET_URL: z.string().url(),
  ALLOWED_ORIGINS: z
    .string()
    .transform((str) => str.split(',').map((s) => s.trim()))
    .default('http://localhost:3000,http://127.0.0.1:3000'),
  ALLOW_PRODUCTION_REGISTRATION: z
    .enum(['true', 'false'])
    .transform((val) => val === 'true')
    .default('false'),

  TEST_ACCOUNT_USERNAME: z
    .string()
    .min(6, 'Username must be at least 6 characters')
    .max(16, 'Username must not exceed 16 characters')
    .regex(/^[a-zA-Z0-9]+$/, 'Username must be alphanumeric'),
  TEST_ACCOUNT_PASSWORD: z
    .string()
    .min(8, 'Password must be at least 8 characters')
    .optional()
    .default('DummyPassword123!'),
  TEST_ACCOUNT_EMAIL: z.string().email(),

  PROTON_MAIL_URL: z.string().url().default('https://mail.proton.me/'),
  USE_MOCK_MAILBOX: z
    .enum(['true', 'false'])
    .transform((val) => val === 'true')
    .default('true'),
  LOCAL_SMTP_PORT: z.coerce.number().int().min(1).max(65535).default(2525),

  HEADLESS: z
    .enum(['true', 'false'])
    .transform((val) => val === 'true')
    .default('true'),
  BROWSER_TIMEOUT_MS: z.coerce.number().positive().default(30000),
  OPERATOR_TIMEOUT_MS: z.coerce.number().positive().default(120000),

  MAX_RETRIES: z.coerce.number().int().min(0).max(10).default(3),
  BASE_RETRY_DELAY_MS: z.coerce.number().positive().default(2000),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),

  RECAPTCHA_V2_SANDBOX_KEY: z.string().default('6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'),
  CLOUDFLARE_TURNSTILE_SANDBOX_KEY: z.string().default('1x00000000000000000000AA'),
  HCAPTCHA_SANDBOX_KEY: z.string().default('10000000-ffff-ffff-ffff-000000000001'),
  SANDBOX_MODE: z
    .enum(['true', 'false'])
    .transform((val) => val === 'true')
    .default('true'),
});

export type Environment = z.infer<typeof RawEnvironmentSchema>;

/**
 * Validates that target URL origin is in the allowlist and enforces production safety guards.
 */
export function validateEnvironment(env: Environment): Environment {
  const targetOrigin = new URL(env.TEST_TARGET_URL).origin;
  const isAllowed = env.ALLOWED_ORIGINS.some((allowed) => {
    try {
      return new URL(allowed).origin === targetOrigin;
    } catch {
      return false;
    }
  });

  if (!isAllowed) {
    throw new Error(
      `Target URL origin '${targetOrigin}' is not in ALLOWED_ORIGINS allowlist: [${env.ALLOWED_ORIGINS.join(', ')}]`
    );
  }

  const isLocalHost = targetOrigin.includes('localhost') || targetOrigin.includes('127.0.0.1');

  // Hard safety guard: Prevent registering on live production systems unless explicitly authorized
  if (!isLocalHost && !env.ALLOW_PRODUCTION_REGISTRATION) {
    throw new Error(
      `Refusing execution against non-local origin '${targetOrigin}'. ALLOW_PRODUCTION_REGISTRATION must be explicitly 'true' for authorized testing.`
    );
  }

  return env;
}

/**
 * Loads and validates environment variables.
 * Never exposes credentials in thrown validation errors.
 */
export function loadConfig(rawEnv: Record<string, any> = process.env): Environment {
  const parseResult = RawEnvironmentSchema.safeParse(rawEnv);

  if (!parseResult.success) {
    // Sanitize issues to ensure TEST_ACCOUNT_PASSWORD is never displayed
    const sanitizedErrors = parseResult.error.issues.map((issue) => {
      if (issue.path.includes('TEST_ACCOUNT_PASSWORD')) {
        return {
          path: issue.path,
          message: 'Invalid password format (details omitted for security)',
        };
      }
      return { path: issue.path, message: issue.message };
    });

    throw new Error(`Configuration Validation Error: ${JSON.stringify(sanitizedErrors)}`);
  }

  return validateEnvironment(parseResult.data);
}
