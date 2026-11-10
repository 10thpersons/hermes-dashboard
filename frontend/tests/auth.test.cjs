// Node stdlib tests plus the existing TypeScript dev dependency. No network or Next server.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.resolve(__dirname, '..');

function keyPolicy(env) {
  const source = fs.readFileSync(path.join(root, 'lib/dashboard-key.ts'), 'utf8');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2017 },
  }).outputText;
  const exports = {};
  new Function('exports', 'process', compiled)(exports, { env });
  return exports.dashboardKey();
}

test('key policy fails closed and preserves explicit dummy material', () => {
  const dummy = '0123456789abcdef'.repeat(4);
  for (const key of [undefined, '', 'short', 'a'.repeat(64), ' '.repeat(64), dummy + '\n', 'é'.repeat(64)]) {
    assert.equal(keyPolicy({ DASHBOARD_API_KEY: key }), null);
  }
  assert.equal(keyPolicy({ DASHBOARD_API_KEY: dummy }), dummy);
});

test('all authentication entry points use the shared policy without a fallback', () => {
  for (const file of ['app/api/login/route.ts', 'middleware.ts', 'app/api/proxy/[...path]/route.ts']) {
    const source = fs.readFileSync(path.join(root, file), 'utf8');
    assert.match(source, /dashboardKey\(\)/);
    assert.match(source, /status: 503/);
    assert.doesNotMatch(source, /process\.env\.DASHBOARD_API_KEY\s*\|\|/);
  }
});

test('rotating forwarded headers cannot reset a trusted peer lockout', async () => {
  const { createLoginLimiter, loginIdentity } = await import('../lib/login-limiter.mjs');
  let time = 1000;
  const limiter = createLoginLimiter(() => time);
  function headers(peer, forwarded) {
    return new Map([['x-dashboard-client-ip', peer], ['x-forwarded-for', forwarded]]);
  }
  for (let i = 0; i < 5; i++) {
    const id = loginIdentity(headers('192.0.2.1', `spoof-${i}`));
    assert.equal(limiter.check(id).allowed, true);
    limiter.fail(id);
  }
  assert.equal(limiter.check(loginIdentity(headers('192.0.2.1', 'fresh'))).allowed, false);
  assert.equal(limiter.check(loginIdentity(headers('192.0.2.2', 'fresh'))).allowed, true);
  for (let i = 0; i < 5; i++) {
    const id = loginIdentity(new Map([['x-forwarded-for', `untrusted-${i}`]]));
    limiter.fail(id);
  }
  assert.equal(limiter.check(loginIdentity(new Map())).allowed, false);
  time += 30000;
  assert.equal(limiter.check('192.0.2.1').allowed, true);
});

test('capacity fails closed without evicting lockouts; expiry frees capacity', async () => {
  const { createLoginLimiter } = await import('../lib/login-limiter.mjs');
  let time = 0;
  const limiter = createLoginLimiter(() => time, 2);
  for (let i = 0; i < 5; i++) limiter.fail('peer-a');
  limiter.fail('peer-b');
  assert.equal(limiter.check('peer-c').allowed, false);
  assert.equal(limiter.check('peer-a').allowed, false);
  time = 60000;
  assert.equal(limiter.check('peer-c').allowed, true);
  limiter.fail('peer-c');
  limiter.clear('peer-c');
  assert.equal(limiter.check('peer-c').allowed, true);
});

test('checked-in ingress overwrites identity and frontend has no host port', () => {
  const nginx = fs.readFileSync(path.join(root, '../nginx.conf'), 'utf8');
  assert.match(nginx, /proxy_set_header X-Dashboard-Client-IP \$remote_addr;/);
  const compose = fs.readFileSync(path.join(root, '../docker-compose.yml'), 'utf8');
  const frontend = compose.split('\n  frontend:')[1].split('\n  nginx:')[0];
  assert.doesNotMatch(frontend, /\n    ports:/);
  assert.match(frontend, /\n    expose:/);
  assert.equal((compose.match(/DASHBOARD_API_KEY:\?/g) || []).length, 2);
});
