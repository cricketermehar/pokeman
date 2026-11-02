import * as fs from 'fs';
import * as path from 'path';
import * as winston from 'winston';

const SENSITIVE_KEYS = new Set([
  'password',
  'passwd',
  'pass',
  'pwd',
  'token',
  'secret',
  'authorization',
  'cookie',
  'set-cookie',
  'activationurl',
  'activation_url',
  'session',
]);

/**
 * Recursively redacts sensitive keys and values from log messages and nested metadata objects.
 */
export function sanitizeData(data: any): any {
  if (data === null || data === undefined) {
    return data;
  }

  if (typeof data === 'string') {
    // Redact sensitive query parameters or key-value pairs in strings
    return data
      .replace(/(password|token|secret|pass|pwd)=([^\s&]+)/gi, '$1=[REDACTED]')
      .replace(/(activated\/)[a-zA-Z0-9_-]+/gi, '$1[TOKEN_REDACTED]');
  }

  if (Array.isArray(data)) {
    return data.map((item) => sanitizeData(item));
  }

  if (typeof data === 'object') {
    const sanitized: Record<string, any> = {};
    for (const [key, val] of Object.entries(data)) {
      const lowerKey = key.toLowerCase();
      if (SENSITIVE_KEYS.has(lowerKey)) {
        sanitized[key] = '[REDACTED]';
      } else {
        sanitized[key] = sanitizeData(val);
      }
    }
    return sanitized;
  }

  return data;
}

const ensureLogDirectory = () => {
  const logDir = path.resolve('logs');
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }
};

ensureLogDirectory();

const deepSanitizerFormat = winston.format((info) => {
  return sanitizeData(info);
});

export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    deepSanitizerFormat(),
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.printf(({ timestamp, level, message, correlationId, ...meta }) => {
          const cid = correlationId ? ` [${correlationId}]` : '';
          const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
          return `[${timestamp}] [${level}]${cid}: ${message}${metaStr}`;
        })
      ),
    }),
    new winston.transports.File({
      filename: 'logs/automation.jsonl',
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 5,
    }),
  ],
});
