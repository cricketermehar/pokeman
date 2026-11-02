import * as http from 'http';

export interface TestAppServer {
  server: http.Server;
  port: number;
  lastGeneratedToken?: string;
  close: () => Promise<void>;
}

export function startTestApp(port: number = 3000): Promise<TestAppServer> {
  let lastToken: string | undefined;

  const server = http.createServer((req, res) => {
    const parsedUrl = new URL(req.url || '/', `http://localhost:${port}`);
    const pathname = parsedUrl.pathname;

    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
      res.writeHead(200);
      res.end();
      return;
    }

    // 1. GET /signup (Registration Form with sandbox CAPTCHA widget)
    if ((pathname === '/signup' || pathname === '/') && (req.method === 'GET' || req.method === 'HEAD')) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      if (req.method === 'HEAD') {
        res.end();
        return;
      }
      res.end(`
        <!DOCTYPE html>
        <html>
        <head><title>Authorized Test Registration Portal</title></head>
        <body style="font-family: sans-serif; padding: 2rem;">
          <h2>Test Account Registration</h2>
          <form id="signup-form" method="POST" action="/api/register">
            <div>
              <label>Username: <input type="text" name="username" id="id_username" required></label>
            </div><br/>
            <div>
              <label>Email: <input type="email" name="email" id="id_email" required></label>
            </div><br/>
            <div>
              <label>Confirm Email: <input type="email" name="confirm_email" id="id_confirm_email" required></label>
            </div><br/>
            <div>
              <label>Password: <input type="password" name="password" id="id_password" required></label>
            </div><br/>
            <div>
              <label>Confirm Password: <input type="password" name="confirm_password" id="id_confirm_password" required></label>
            </div><br/>
            <div>
              <label><input type="checkbox" name="terms" id="id_terms" checked> I accept the Terms of Service</label>
            </div><br/>
            
            <!-- Simulated Sandbox Challenge Container -->
            <div id="captcha-container" class="g-recaptcha" data-sitekey="6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI">
              <textarea name="g-recaptcha-response" id="g-recaptcha-response" style="display:none;">SANDBOX_TOKEN_PASSED</textarea>
              <button type="button" id="sandbox-solve-btn" onclick="document.getElementById('g-recaptcha-response').value='SANDBOX_TOKEN_PASSED'; document.getElementById('status-msg').innerText='✅ Challenge Auto-Verified (Sandbox)';">
                [Sandbox] Verified Automatically
              </button>
              <span id="status-msg" style="color: green; margin-left: 10px; font-weight: bold;">✅ Challenge Auto-Verified (Sandbox)</span>
            </div><br/>

            <button type="submit" id="submit-btn">Register Account</button>
          </form>
        </body>
        </html>
      `);
      return;
    }

    // 2. POST /api/register (Handle Form Submission)
    if (pathname === '/api/register' && req.method === 'POST') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk.toString();
      });

      req.on('end', () => {
        const formData = new URLSearchParams(body);
        const username = formData.get('username') || '';
        const email = formData.get('email') || '';
        const captchaResponse = formData.get('g-recaptcha-response') || '';

        if (!captchaResponse) {
          res.writeHead(400, { 'Content-Type': 'text/html' });
          res.end('<h1>400 Bad Request - Security challenge token missing</h1>');
          return;
        }

        // Generate mock activation token
        lastToken = `tok_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(`
          <!DOCTYPE html>
          <html>
          <body>
            <h2>Registration Submitted Successfully</h2>
            <p id="confirmation-msg">Welcome ${username}! An activation link has been dispatched to ${email}.</p>
          </body>
          </html>
        `);
      });
      return;
    }

    // 3. GET /profile/activated/:token (Activation Landing Page)
    if (pathname.includes('/profile/activated/') || pathname.includes('/activate/')) {
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end(`
        <!DOCTYPE html>
        <html>
        <body>
          <h1 id="success-banner">Account Successfully Activated!</h1>
          <p>Your test trainer profile is verified and active.</p>
        </body>
        </html>
      `);
      return;
    }

    // 4. Helper endpoint to inspect last generated token
    if (pathname === '/api/last-token') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ token: lastToken }));
      return;
    }

    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('Not Found');
  });

  return new Promise((resolve) => {
    server.listen(port, () => {
      resolve({
        server,
        port,
        get lastGeneratedToken() {
          return lastToken;
        },
        close: () =>
          new Promise<void>((closeResolve) => {
            server.close(() => closeResolve());
          }),
      });
    });
  });
}

if (require.main === module) {
  startTestApp(3000).then((s) => {
    console.log(`Test App Server listening on http://localhost:${s.port}/signup`);
  });
}
