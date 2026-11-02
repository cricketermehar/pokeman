import * as fs from 'fs';
import * as path from 'path';
import { chromium, Browser, BrowserContext, Page } from 'playwright';
import { Environment } from '../config/environment';
import { SessionManager } from './session.manager';
import { logger } from './logger.service';

export class BrowserService {
  private browser: Browser | null = null;
  private activeContexts: Set<BrowserContext> = new Set();
  private isShuttingDown: boolean = false;

  constructor(private config: Environment) {
    this.registerProcessHooks();
  }

  getBrowserInstance(): Browser | null {
    return this.browser;
  }

  getActiveContexts(): BrowserContext[] {
    return Array.from(this.activeContexts);
  }

  private registerProcessHooks(): void {
    const cleanup = async () => {
      if (!this.isShuttingDown) {
        this.isShuttingDown = true;
        await this.teardown();
      }
    };
    process.once('SIGINT', cleanup);
    process.once('SIGTERM', cleanup);
  }

  async initialize(): Promise<void> {
    if (this.browser) {
      return;
    }

    // Launch official Chromium without anti-detection tampering or insecure sandbox disables
    this.browser = await chromium.launch({
      headless: this.config.HEADLESS,
      timeout: this.config.BROWSER_TIMEOUT_MS,
    });

    logger.info('Playwright Chromium initialized', {
      headless: this.config.HEADLESS,
      timeoutMs: this.config.BROWSER_TIMEOUT_MS,
    });
  }

  async createContext(sessionName?: string, enableTracing: boolean = true): Promise<BrowserContext> {
    if (!this.browser) {
      await this.initialize();
    }

    const contextOptions: Parameters<Browser['newContext']>[0] = {
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: false, // Enforce strict TLS validation
    };

    if (sessionName && SessionManager.hasValidSession(sessionName)) {
      contextOptions.storageState = SessionManager.getSessionPath(sessionName);
      logger.info('Restored session state in context', { sessionName });
    }

    const context = await this.browser!.newContext(contextOptions);
    this.activeContexts.add(context);

    if (enableTracing) {
      try {
        await context.tracing.start({ screenshots: true, snapshots: true });
      } catch (err: any) {
        if (!err.message?.includes('already started')) {
          throw err;
        }
      }
    }

    return context;
  }

  async captureScreenshot(page: Page, label: string): Promise<string> {
    const dir = path.resolve('logs/screenshots');
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const sanitizedLabel = label.replace(/[^a-zA-Z0-9_-]/g, '_');
    const filename = path.join(dir, `${sanitizedLabel}_${Date.now()}.png`);
    await page.screenshot({ path: filename, fullPage: true });
    logger.info('Diagnostic screenshot saved', { path: filename });
    return filename;
  }

  async closeContext(context: BrowserContext, traceFilename?: string): Promise<void> {
    try {
      if (traceFilename) {
        const traceDir = path.resolve('logs/traces');
        if (!fs.existsSync(traceDir)) {
          fs.mkdirSync(traceDir, { recursive: true });
        }
        const fullTracePath = path.join(traceDir, `${traceFilename}_trace.zip`);
        await context.tracing.stop({ path: fullTracePath });
        logger.info('Saved Playwright trace bundle', { path: fullTracePath });
      }
    } catch {
      // Ignore tracing stop errors if already stopped or not started
    } finally {
      this.activeContexts.delete(context);
      try {
        await context.close();
      } catch {}
    }
  }

  async teardown(): Promise<void> {
    for (const ctx of Array.from(this.activeContexts)) {
      try {
        await ctx.close();
      } catch {}
    }
    this.activeContexts.clear();

    if (this.browser) {
      try {
        await this.browser.close();
      } catch {}
      this.browser = null;
      logger.info('Playwright Chromium engine closed cleanly');
    }
  }
}
