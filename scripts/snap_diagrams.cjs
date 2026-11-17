#!/usr/bin/env node
/**
 * Render generated diagram HTML files (#diagram SVG) into 2x DPI PNGs.
 * Cross-platform (Windows / macOS / Linux):
 *   1. Uses Playwright / playwright-core when available (local, global, or npx cache).
 *   2. Falls back to zero-dependency Chrome/Edge DevTools Protocol (CDP) when
 *      Playwright is not installed, using system Microsoft Edge or Google Chrome.
 */
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { pathToFileURL } = require('url');

function uniqueExistingDirs(dirs) {
  const seen = new Set();
  const out = [];
  for (const d of dirs) {
    if (!d) continue;
    const resolved = path.resolve(d);
    if (!seen.has(resolved) && fs.existsSync(resolved)) {
      seen.add(resolved);
      out.push(resolved);
    }
  }
  return out;
}

function getNpxCacheDirs() {
  const dirs = [];
  if (process.env.npm_config_cache) {
    dirs.push(path.join(process.env.npm_config_cache, '_npx'));
  }
  if (process.platform === 'win32') {
    const localAppData = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    dirs.push(path.join(localAppData, 'npm-cache', '_npx'));
  }
  dirs.push(path.join(os.homedir(), '.npm', '_npx'));
  return uniqueExistingDirs(dirs);
}

function getGlobalNodeModulesDirs() {
  const dirs = [];
  if (process.env.NODE_PATH) {
    for (const p of process.env.NODE_PATH.split(path.delimiter)) {
      dirs.push(p);
    }
  }
  if (process.env.APPDATA) {
    dirs.push(path.join(process.env.APPDATA, 'npm', 'node_modules'));
  }
  if (process.env.npm_config_prefix) {
    dirs.push(path.join(process.env.npm_config_prefix, 'node_modules'));
    dirs.push(path.join(process.env.npm_config_prefix, 'lib', 'node_modules'));
  }
  const execDir = path.dirname(process.execPath);
  dirs.push(path.join(execDir, 'node_modules'));
  dirs.push(path.join(execDir, '..', 'lib', 'node_modules'));
  if (process.platform !== 'win32') {
    dirs.push('/usr/local/lib/node_modules');
    dirs.push('/opt/homebrew/lib/node_modules');
  }
  return uniqueExistingDirs(dirs);
}

function findPlaywright() {
  const packages = ['playwright', 'playwright-core'];
  const searchRoots = uniqueExistingDirs([
    path.join(process.cwd(), 'node_modules'),
    path.join(__dirname, 'node_modules'),
    path.join(path.dirname(__dirname), 'node_modules'),
    ...getGlobalNodeModulesDirs(),
  ]);

  for (const pkg of packages) {
    try {
      return { mod: require(pkg), packageName: pkg, source: 'require' };
    } catch (_) {}
    for (const root of searchRoots) {
      const cand = path.join(root, pkg);
      if (fs.existsSync(cand)) {
        return { mod: require(cand), packageName: pkg, source: cand };
      }
    }
  }

  for (const npxDir of getNpxCacheDirs()) {
    let subs = [];
    try {
      subs = fs.readdirSync(npxDir);
    } catch (_) {
      continue;
    }
    for (const pkg of packages) {
      for (const sub of subs) {
        const cand = path.join(npxDir, sub, 'node_modules', pkg);
        if (fs.existsSync(cand)) {
          return { mod: require(cand), packageName: pkg, source: cand };
        }
      }
    }
  }
  return null;
}

function findExecutableInPath(names) {
  const pathEnv = process.env.PATH || '';
  const dirs = pathEnv.split(path.delimiter).filter(Boolean);
  for (const dir of dirs) {
    for (const name of names) {
      const cand = path.join(dir, name);
      if (fs.existsSync(cand)) return cand;
    }
  }
  return undefined;
}

function findChromeExecutable() {
  const envOverrides = [
    process.env.CHROME_PATH,
    process.env.EDGE_PATH,
    process.env.BROWSER_PATH,
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    process.env.PUPPETEER_EXECUTABLE_PATH,
  ];
  for (const p of envOverrides) {
    if (p && fs.existsSync(p)) return p;
  }

  const candidates = [];
  if (process.platform === 'win32') {
    const pf = process.env.ProgramFiles || 'C:\\Program Files';
    const pf86 = process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)';
    const lad = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    const rels = [
      path.join('Google', 'Chrome', 'Application', 'chrome.exe'),
      path.join('Microsoft', 'Edge', 'Application', 'msedge.exe'),
      path.join('Chromium', 'Application', 'chrome.exe'),
      path.join('BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe'),
    ];
    for (const base of [pf, pf86, lad]) {
      for (const rel of rels) {
        candidates.push(path.join(base, rel));
      }
    }
  } else if (process.platform === 'darwin') {
    const homeApps = path.join(os.homedir(), 'Applications');
    const appRels = [
      'Google Chrome.app/Contents/MacOS/Google Chrome',
      'Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
      'Chromium.app/Contents/MacOS/Chromium',
      'Brave Browser.app/Contents/MacOS/Brave Browser',
    ];
    for (const base of ['/Applications', homeApps]) {
      for (const rel of appRels) {
        candidates.push(path.join(base, rel));
      }
    }
  } else {
    candidates.push(
      '/usr/bin/google-chrome',
      '/usr/bin/google-chrome-stable',
      '/usr/bin/microsoft-edge',
      '/usr/bin/chromium',
      '/usr/bin/chromium-browser',
      '/snap/bin/chromium'
    );
  }

  for (const p of candidates) {
    if (p && fs.existsSync(p)) return p;
  }

  const pathNames = process.platform === 'win32'
    ? ['chrome.exe', 'msedge.exe', 'chromium.exe']
    : ['google-chrome', 'google-chrome-stable', 'microsoft-edge', 'chromium', 'chromium-browser'];
  return findExecutableInPath(pathNames);
}

function httpGetJson(url, method = 'GET') {
  return new Promise((resolve, reject) => {
    const req = http.request(url, { method }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        if (res.statusCode && res.statusCode >= 400) {
          reject(new Error(`HTTP ${res.statusCode} for ${method} ${url}: ${body}`));
          return;
        }
        try {
          resolve(JSON.parse(body));
        } catch (err) {
          reject(new Error(`Invalid JSON from ${url}: ${err.message}`));
        }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function connectWs(wsUrl) {
  return new Promise((resolve, reject) => {
    const u = new URL(wsUrl);
    const key = crypto.randomBytes(16).toString('base64');
    const req = http.request({
      host: u.hostname,
      port: Number(u.port),
      path: u.pathname + u.search,
      headers: {
        Connection: 'Upgrade',
        Upgrade: 'websocket',
        'Sec-WebSocket-Key': key,
        'Sec-WebSocket-Version': '13',
      },
    });

    req.on('error', reject);
    req.on('upgrade', (res, socket, head) => {
      let buf = head && head.length ? Buffer.from(head) : Buffer.alloc(0);
      let fragOpcode = 0;
      let fragChunks = [];
      const listeners = { message: [], close: [], error: [] };

      function sendFrame(opcode, payloadBuf) {
        const len = payloadBuf.length;
        const mask = crypto.randomBytes(4);
        let header;
        if (len < 126) {
          header = Buffer.alloc(6);
          header[0] = 0x80 | opcode;
          header[1] = 0x80 | len;
          mask.copy(header, 2);
        } else if (len <= 0xffff) {
          header = Buffer.alloc(8);
          header[0] = 0x80 | opcode;
          header[1] = 0x80 | 126;
          header.writeUInt16BE(len, 2);
          mask.copy(header, 4);
        } else {
          header = Buffer.alloc(14);
          header[0] = 0x80 | opcode;
          header[1] = 0x80 | 127;
          header.writeBigUInt64BE(BigInt(len), 2);
          mask.copy(header, 10);
        }
        const masked = Buffer.allocUnsafe(len);
        for (let i = 0; i < len; i += 1) {
          masked[i] = payloadBuf[i] ^ mask[i & 3];
        }
        socket.write(Buffer.concat([header, masked]));
      }

      function processFrames() {
        while (buf.length >= 2) {
          const b0 = buf[0];
          const b1 = buf[1];
          const fin = (b0 & 0x80) !== 0;
          const opcode = b0 & 0x0f;
          const isMasked = (b1 & 0x80) !== 0;
          let payloadLen = b1 & 0x7f;
          let offset = 2;

          if (payloadLen === 126) {
            if (buf.length < 4) return;
            payloadLen = buf.readUInt16BE(2);
            offset = 4;
          } else if (payloadLen === 127) {
            if (buf.length < 10) return;
            payloadLen = Number(buf.readBigUInt64BE(2));
            offset = 10;
          }

          const maskBytes = isMasked ? 4 : 0;
          if (buf.length < offset + maskBytes + payloadLen) return;

          let payload = buf.subarray(offset + maskBytes, offset + maskBytes + payloadLen);
          if (isMasked) {
            const maskKey = buf.subarray(offset, offset + 4);
            const unmasked = Buffer.allocUnsafe(payloadLen);
            for (let i = 0; i < payloadLen; i += 1) {
              unmasked[i] = payload[i] ^ maskKey[i & 3];
            }
            payload = unmasked;
          }
          buf = buf.subarray(offset + maskBytes + payloadLen);

          if (opcode === 0x8) {
            socket.end();
            return;
          }
          if (opcode === 0x9) {
            sendFrame(0x0a, payload);
            continue;
          }
          if (opcode === 0x0a) continue;

          if (opcode !== 0x0) {
            fragOpcode = opcode;
            fragChunks = [payload];
          } else {
            fragChunks.push(payload);
          }

          if (fin) {
            const fullPayload = fragChunks.length === 1 ? fragChunks[0] : Buffer.concat(fragChunks);
            fragChunks = [];
            if (fragOpcode === 0x1) {
              const text = fullPayload.toString('utf8');
              for (const fn of listeners.message) fn(text);
            }
          }
        }
      }

      socket.on('data', (chunk) => {
        buf = buf.length ? Buffer.concat([buf, chunk]) : chunk;
        processFrames();
      });
      socket.on('close', () => {
        for (const fn of listeners.close) fn();
      });
      socket.on('error', (err) => {
        for (const fn of listeners.error) fn(err);
      });

      resolve({
        sendText(text) {
          sendFrame(0x1, Buffer.from(text, 'utf8'));
        },
        close() {
          try { sendFrame(0x8, Buffer.alloc(0)); } catch (_) {}
          socket.destroy();
        },
        on(evt, fn) {
          if (listeners[evt]) listeners[evt].push(fn);
        },
      });
    });
    req.end();
  });
}

async function createCdpSession(wsUrl) {
  const ws = await connectWs(wsUrl);
  let nextId = 1;
  const pending = new Map();
  const eventWaiters = new Map();

  ws.on('message', (raw) => {
    const msg = JSON.parse(raw);
    if (msg.id) {
      const entry = pending.get(msg.id);
      if (entry) {
        pending.delete(msg.id);
        if (msg.error) {
          entry.reject(new Error(`CDP ${entry.method}: ${msg.error.message}`));
        } else {
          entry.resolve(msg.result || {});
        }
      }
      return;
    }
    if (msg.method && eventWaiters.has(msg.method)) {
      const queue = eventWaiters.get(msg.method);
      eventWaiters.delete(msg.method);
      for (const fn of queue) fn(msg.params || {});
    }
  });

  ws.on('close', () => {
    for (const entry of pending.values()) {
      entry.reject(new Error('CDP WebSocket closed unexpectedly'));
    }
    pending.clear();
  });

  return {
    send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = nextId++;
        pending.set(id, { resolve, reject, method });
        ws.sendText(JSON.stringify({ id, method, params }));
      });
    },
    waitForEvent(method, timeoutMs = 15000) {
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          reject(new Error(`Timed out waiting for CDP event ${method}`));
        }, timeoutMs);
        const list = eventWaiters.get(method) || [];
        list.push((params) => {
          clearTimeout(timer);
          resolve(params);
        });
        eventWaiters.set(method, list);
      });
    },
    close() {
      ws.close();
    },
  };
}

function launchHeadlessBrowser(executablePath, userDataDir, headlessFlag) {
  return new Promise((resolve, reject) => {
    const args = [
      headlessFlag,
      '--remote-debugging-port=0',
      `--user-data-dir=${userDataDir}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-gpu',
      '--disable-extensions',
      '--disable-background-networking',
      '--disable-sync',
      '--mute-audio',
      ...(process.platform === 'linux' ? ['--no-sandbox'] : []),
      'about:blank',
    ];
    const child = spawn(executablePath, args, { stdio: ['ignore', 'ignore', 'pipe'] });
    let stderr = '';
    let settled = false;

    const timer = setTimeout(() => {
      if (!settled) {
        settled = true;
        try { child.kill(); } catch (_) {}
        reject(new Error(`Browser launch timed out (${executablePath}): ${stderr}`));
      }
    }, 15000);

    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString('utf8');
      const m = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (m && !settled) {
        settled = true;
        clearTimeout(timer);
        resolve({ child, browserWsUrl: m[1] });
      }
    });

    child.on('error', (err) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(err);
      }
    });

    child.on('exit', (code) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        reject(new Error(`Browser exited with code ${code} before DevTools started: ${stderr}`));
      }
    });
  });
}

async function rmDirWithRetry(dirPath) {
  for (let i = 0; i < 6; i += 1) {
    try {
      fs.rmSync(dirPath, { recursive: true, force: true });
      return;
    } catch (_) {
      await new Promise((r) => setTimeout(r, 120));
    }
  }
}

async function findPageTargetWs(port) {
  const deadline = Date.now() + 4000;
  while (Date.now() < deadline) {
    try {
      const list = await httpGetJson(`http://127.0.0.1:${port}/json/list`);
      const page = Array.isArray(list) ? list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl) : null;
      if (page) return page.webSocketDebuggerUrl;
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 100));
  }
  const created = await httpGetJson(`http://127.0.0.1:${port}/json/new?about:blank`, 'PUT');
  if (created && created.webSocketDebuggerUrl) return created.webSocketDebuggerUrl;
  throw new Error('Could not obtain CDP page WebSocket URL');
}

async function renderWithPlaywright(pwInfo, executablePath, targetDir, files) {
  const { chromium } = pwInfo.mod;
  if (pwInfo.packageName === 'playwright-core' && !executablePath) {
    throw new Error('playwright-core found, but no system Chrome/Edge executable was detected.');
  }
  const launchArgs = process.platform === 'linux'
    ? ['--no-sandbox', '--disable-gpu']
    : ['--disable-gpu'];
  const browser = await chromium.launch({
    ...(executablePath ? { executablePath } : {}),
    headless: true,
    args: launchArgs,
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1400, height: 1100 },
      deviceScaleFactor: 2,
    });
    const page = await context.newPage();
    for (const file of files) {
      const fullHtml = path.join(targetDir, file);
      const outPng = path.join(targetDir, file.replace(/\.html$/i, '.png'));
      const fileUrl = pathToFileURL(path.resolve(fullHtml)).href;
      await page.goto(fileUrl, { waitUntil: 'load' });
      await page.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve()));
      const svg = await page.$('#diagram');
      if (!svg) throw new Error(`Missing #diagram in ${file}`);
      await svg.screenshot({ path: outPng, type: 'png' });
      console.log('Rendered:', outPng);
    }
  } finally {
    await browser.close();
  }
}

async function renderWithCdp(executablePath, targetDir, files) {
  const tmpProfile = fs.mkdtempSync(path.join(os.tmpdir(), 'sdd-cdp-'));
  let browserProc = null;
  let cdp = null;
  try {
    let launched;
    try {
      launched = await launchHeadlessBrowser(executablePath, tmpProfile, '--headless=new');
    } catch (_) {
      launched = await launchHeadlessBrowser(executablePath, tmpProfile, '--headless');
    }
    browserProc = launched.child;
    const port = new URL(launched.browserWsUrl).port;
    const pageWsUrl = await findPageTargetWs(port);
    cdp = await createCdpSession(pageWsUrl);

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');

    for (const file of files) {
      const fullHtml = path.join(targetDir, file);
      const outPng = path.join(targetDir, file.replace(/\.html$/i, '.png'));
      const fileUrl = pathToFileURL(path.resolve(fullHtml)).href;

      await cdp.send('Emulation.setDeviceMetricsOverride', {
        width: 1400,
        height: 1100,
        deviceScaleFactor: 2,
        mobile: false,
      });

      const loaded = cdp.waitForEvent('Page.loadEventFired', 15000);
      await cdp.send('Page.navigate', { url: fileUrl });
      await loaded;

      await cdp.send('Runtime.evaluate', {
        expression: `(async () => {
          if (document.fonts && document.fonts.ready) await document.fonts.ready;
          await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
        })()`,
        awaitPromise: true,
      });

      const evalRes = await cdp.send('Runtime.evaluate', {
        expression: `(() => {
          const el = document.querySelector('#diagram');
          if (!el) return null;
          const r = el.getBoundingClientRect();
          return { x: r.x, y: r.y, width: r.width, height: r.height };
        })()`,
        returnByValue: true,
      });
      const rect = evalRes && evalRes.result && evalRes.result.value;
      if (!rect || rect.width <= 0 || rect.height <= 0) {
        throw new Error(`Missing or empty #diagram in ${file}`);
      }

      const needW = Math.max(1400, Math.ceil(rect.x + rect.width + 20));
      const needH = Math.max(1100, Math.ceil(rect.y + rect.height + 20));
      if (needW > 1400 || needH > 1100) {
        await cdp.send('Emulation.setDeviceMetricsOverride', {
          width: needW,
          height: needH,
          deviceScaleFactor: 2,
          mobile: false,
        });
      }

      const shot = await cdp.send('Page.captureScreenshot', {
        format: 'png',
        clip: {
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
          scale: 1,
        },
        captureBeyondViewport: true,
      });
      fs.writeFileSync(outPng, Buffer.from(shot.data, 'base64'));
      console.log('Rendered:', outPng);
    }
  } finally {
    if (cdp) {
      try { cdp.close(); } catch (_) {}
    }
    if (browserProc && !browserProc.killed) {
      try { browserProc.kill(); } catch (_) {}
    }
    await rmDirWithRetry(tmpProfile);
  }
}

function parseArgs(argv) {
  let checkOnly = false;
  let engine = 'auto';
  const positional = [];
  for (const arg of argv) {
    if (arg === '--check') {
      checkOnly = true;
    } else if (arg === '--help' || arg === '-h') {
      console.log('Usage: node snap_diagrams.cjs [--check] [--engine=auto|playwright|cdp] <diagrams_dir>');
      process.exit(0);
    } else if (arg.startsWith('--engine=')) {
      engine = arg.slice('--engine='.length).toLowerCase();
    } else {
      positional.push(arg);
    }
  }
  return { checkOnly, engine, targetDir: positional[0] };
}

(async () => {
  const { checkOnly, engine, targetDir } = parseArgs(process.argv.slice(2));
  const pwInfo = findPlaywright();
  const executablePath = findChromeExecutable();

  if (checkOnly) {
    console.log(JSON.stringify({
      platform: process.platform,
      node: process.version,
      playwright: pwInfo ? { package: pwInfo.packageName, source: pwInfo.source } : null,
      browserExecutable: executablePath || null,
      selectedEngine: pwInfo ? 'playwright' : (executablePath ? 'cdp' : 'none'),
    }, null, 2));
    if (!pwInfo && !executablePath) process.exit(2);
    return;
  }

  if (!targetDir) {
    console.error('Usage: node snap_diagrams.cjs [--check] [--engine=auto|playwright|cdp] <diagrams_dir>');
    process.exit(1);
  }
  if (!fs.existsSync(targetDir)) {
    throw new Error(`Diagrams directory not found: ${targetDir}`);
  }

  const files = fs.readdirSync(targetDir).filter((f) => /\.html$/i.test(f)).sort();
  if (files.length === 0) {
    console.log('No .html diagram files found in:', targetDir);
    return;
  }

  if (engine === 'playwright') {
    if (!pwInfo) throw new Error('Requested --engine=playwright, but playwright/playwright-core was not found.');
    await renderWithPlaywright(pwInfo, executablePath, targetDir, files);
    return;
  }
  if (engine === 'cdp') {
    if (!executablePath) throw new Error('Requested --engine=cdp, but no Chrome/Edge/Chromium executable was found.');
    await renderWithCdp(executablePath, targetDir, files);
    return;
  }

  if (pwInfo && (pwInfo.packageName === 'playwright' || executablePath)) {
    await renderWithPlaywright(pwInfo, executablePath, targetDir, files);
  } else if (executablePath) {
    await renderWithCdp(executablePath, targetDir, files);
  } else {
    throw new Error(
      'Neither Playwright nor a system Chrome/Edge/Chromium browser was found.\n' +
      'Fix options:\n' +
      '  - Windows: install Microsoft Edge or Google Chrome (or set CHROME_PATH), or run `npm install playwright && npx playwright install chromium`\n' +
      '  - macOS/Linux: install Google Chrome / Chromium, or run `npm install playwright && npx playwright install chromium`'
    );
  }
})().catch((err) => {
  console.error('[snap_diagrams] ERROR:', err && err.stack ? err.stack : err);
  process.exit(1);
});
