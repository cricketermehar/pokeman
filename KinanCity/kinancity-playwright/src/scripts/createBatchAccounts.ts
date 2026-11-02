import * as fs from 'fs';
import * as path from 'path';
import { loadConfig } from '../config/environment';
import { BrowserService } from '../core/browser.service';
import { RetryManager } from '../core/retry.manager';
import { CaptchaService } from '../services/captcha.service';
import { EmailVerificationService } from '../services/email.service';
import { RegistrationService } from '../services/registration.service';
import { MockMailboxAdapter } from '../adapters/mock-mailbox.adapter';
import { WorkflowOrchestrator } from '../runner';
import { logger } from '../core/logger.service';

interface BatchAccountSpec {
  username: string;
  password: string;
  email: string;
}

async function runBatch(count: number = 5, orderId?: string) {
  const currentOrderId = orderId || `ORD-${Date.now().toString().slice(-4)}`;
  console.log('════════════════════════════════════════════════════════════');
  console.log(`  KinanCity Automated Sandbox Batch Creator`);
  console.log(`  Order: ${currentOrderId} | Target: ${count} Accounts`);
  console.log('════════════════════════════════════════════════════════════\n');

  const baseConfig = loadConfig();
  const testServerOrigin = new URL(baseConfig.TEST_TARGET_URL).origin;

  const browserService = new BrowserService(baseConfig);
  await browserService.initialize();

  const retryManager = new RetryManager({
    maxRetries: 2,
    baseDelayMs: 500,
  });

  const captchaService = new CaptchaService(baseConfig.OPERATOR_TIMEOUT_MS, 500, true);
  const registrationService = new RegistrationService(captchaService);
  const mailboxAdapter = new MockMailboxAdapter(testServerOrigin);

  const results: Array<{
    index: number;
    username: string;
    email: string;
    success: boolean;
    durationSeconds: string;
    error?: string;
  }> = [];

  const createdFile = path.resolve('created_accounts.txt');
  const ordersDir = path.resolve('orders');
  if (!fs.existsSync(ordersDir)) {
    fs.mkdirSync(ordersDir, { recursive: true });
  }
  const orderCsvFile = path.join(ordersDir, `${currentOrderId}.csv`);
  if (!fs.existsSync(orderCsvFile)) {
    fs.writeFileSync(
      orderCsvFile,
      '\ufeff#,Order ID,Username,Password,Email Address,Account Status,Creation Engine,Created Timestamp\n',
      'utf-8'
    );
  }

  const accountsToCreate: BatchAccountSpec[] = Array.from({ length: count }, (_, i) => {
    const id = (i + 1).toString().padStart(2, '0');
    const randomSuffix = Math.random().toString(36).substring(2, 6);
    return {
      username: `AutoUser${id}${randomSuffix}`,
      password: `AutoPass${id}!99`,
      email: `autouser${id}_${randomSuffix}@example.com`,
    };
  });

  try {
    for (let i = 0; i < accountsToCreate.length; i++) {
      const spec = accountsToCreate[i];
      const accountConfig = {
        ...baseConfig,
        TEST_ACCOUNT_USERNAME: spec.username,
        TEST_ACCOUNT_PASSWORD: spec.password,
        TEST_ACCOUNT_EMAIL: spec.email,
        OPERATOR_TIMEOUT_MS: 5000,
      };

      const emailService = new EmailVerificationService(mailboxAdapter, accountConfig);
      const orchestrator = new WorkflowOrchestrator(
        browserService,
        registrationService,
        emailService,
        retryManager,
        accountConfig
      );

      console.log(`▶ [${i + 1}/${count}] Creating Account: ${spec.username} (${spec.email}) for Order ${currentOrderId}...`);
      const startTime = Date.now();
      const outcome = await orchestrator.run();
      const durationSeconds = ((Date.now() - startTime) / 1000).toFixed(2);
      const nowStr = new Date().toISOString().replace('T', ' ').substring(0, 19);

      if (outcome.success) {
        console.log(`  ✅ Successfully created and activated in ${durationSeconds}s!\n`);
        fs.appendFileSync(createdFile, `${spec.username}:${spec.password}:${spec.email}:${currentOrderId}\n`, 'utf-8');
        const itemNum = results.filter((r) => r.success).length + 1;
        fs.appendFileSync(
          orderCsvFile,
          `${itemNum},${currentOrderId},${spec.username},${spec.password},${spec.email},ACTIVATED,Sandbox Automation,${nowStr}\n`,
          'utf-8'
        );
      } else {
        console.log(`  ❌ Failed: ${outcome.error} (${durationSeconds}s)\n`);
      }

      results.push({
        index: i + 1,
        username: spec.username,
        email: spec.email,
        success: outcome.success,
        durationSeconds,
        error: outcome.error,
      });

      // Brief delay between accounts
      await new Promise((res) => setTimeout(res, 800));
    }
  } finally {
    await browserService.teardown();
  }

  const successfulCount = results.filter((r) => r.success).length;

  // Write order summary JSON
  const orderMetadata = {
    orderId: currentOrderId,
    createdAt: new Date().toISOString(),
    requestedCount: count,
    completedCount: successfulCount,
    status: successfulCount === count ? 'COMPLETED' : 'PARTIAL',
    csvFile: orderCsvFile,
    accounts: results
      .filter((r) => r.success)
      .map((r) => ({
        username: r.username,
        email: r.email,
        password: accountsToCreate.find((a) => a.username === r.username)?.password || '',
        status: 'ACTIVATED',
        durationSeconds: r.durationSeconds,
      })),
  };
  fs.writeFileSync(path.join(ordersDir, `${currentOrderId}.json`), JSON.stringify(orderMetadata, null, 2), 'utf-8');

  console.log('════════════════════════════════════════════════════════════');
  console.log(`  ORDER ${currentOrderId} SUMMARY`);
  console.log('════════════════════════════════════════════════════════════');
  console.table(
    results.map((r) => ({
      '#': r.index,
      Username: r.username,
      Email: r.email,
      Status: r.success ? '✅ ACTIVATED' : '❌ FAILED',
      Duration: `${r.durationSeconds}s`,
    }))
  );

  console.log(`\nTotal Successfully Activated for Order ${currentOrderId}: ${successfulCount} / ${count}`);
  console.log(`Dedicated Order CSV: ${orderCsvFile}`);
  console.log(`Cumulative Credentials: ${createdFile}\n`);
}

if (require.main === module) {
  const countArg = parseInt(process.argv[2] || '5', 10);
  const count = isNaN(countArg) || countArg <= 0 ? 5 : countArg;
  const orderId = process.argv[3];
  runBatch(count, orderId).catch((err) => {
    console.error('Batch creator failed:', err);
    process.exit(1);
  });
}
