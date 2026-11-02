import * as readline from 'readline';
import * as path from 'path';
import * as fs from 'fs';
import { chromium } from 'playwright';
import { SessionManager } from '../core/session.manager';
import { logger } from '../core/logger.service';

/**
 * Interactive CLI script for initializing an authenticated Proton Mail session.
 * 
 * SECURITY BOUNDARY:
 * - Credentials are NEVER requested, read, or logged by this script.
 * - The human operator interacts directly with Proton Mail's official web UI in a headed browser window.
 * - Cookies/storage tokens are saved locally in the gitignored `sessions/` directory with 0o600 permissions.
 */
async function main() {
  console.log('════════════════════════════════════════════════════════════');
  console.log('  KinanCity — Proton Mail Session Initializer (HITL)');
  console.log('════════════════════════════════════════════════════════════');
  console.log('This utility launches a dedicated Chromium browser window for you to');
  console.log('manually log in to your authorized test mailbox (e.g., Proton Mail).');
  console.log('No passwords or credentials will be captured or logged.\n');

  const sessionName = 'proton';

  const browser = await chromium.launch({
    headless: false,
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });

  const page = await context.newPage();

  logger.info('Navigating to Proton Mail login portal...');
  await page.goto('https://mail.proton.me/login', { waitUntil: 'domcontentloaded' });

  console.log('\n👉 Instructions:');
  console.log('  1. In the opened browser window, log in to your authorized mailbox.');
  console.log('  2. Complete any 2FA, OTP, or security verification challenges directly in the browser.');
  console.log('  3. Once your inbox has fully loaded, return to this terminal and press [ENTER].\n');

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  await new Promise<void>((resolve) => {
    rl.question('Press [ENTER] after you have logged in and can see your inbox: ', () => {
      rl.close();
      resolve();
    });
  });

  console.log('\nCapturing authenticated session state...');
  const sessionFilePath = await SessionManager.persistSession(context, sessionName);
  const validation = SessionManager.validateSessionFile(sessionFilePath);

  if (!validation.isValid) {
    logger.error('Session validation failed!', { reason: validation.reason });
    console.error(`❌ Session validation failed: ${validation.reason}`);
  } else {
    logger.info('Proton Mail session saved and validated successfully.', {
      sessionPath: sessionFilePath,
    });
    console.log(`✅ Session state successfully saved to: ${sessionFilePath}`);
    console.log('Permissions set to 0600 (owner read/write only).');
    console.log('Session is ready for use with authorized email verification adapters.');
  }

  await browser.close();
  console.log('\nInitialization completed cleanly.');
}

if (require.main === module) {
  main().catch((err) => {
    console.error('Fatal error during Proton session initialization:', err);
    process.exit(1);
  });
}
