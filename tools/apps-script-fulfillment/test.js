// Tests for the Apps Script fulfillment code, run with `node test.js`.
//
// The two .gs files are loaded into a sandbox with fakes standing in for Google's
// services (Utilities, UrlFetchApp, MailApp, PropertiesService and so on), so
// nothing here touches Gumroad, Gmail or any real secret.
//
// `node test.js --emit-key <seedHex>` prints one license key signed with that
// seed. tests/test_apps_script_fulfillment.py uses it to check the key with the
// same Python code the Windows app uses.

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const SECRET = 'ping-secret-for-tests';
const PKCS8_PREFIX = Buffer.from('302e020100300506032b657004220420', 'hex');

function signed(buffer) {
  return [...buffer].map((b) => (b > 127 ? b - 256 : b));
}

/** Loads Ed25519.gs and Code.gs into a fresh sandbox with fake Google services. */
function load({ seed = crypto.randomBytes(32), sales = {}, failMail = false } = {}) {
  const store = new Map([
    ['GUMROAD_ACCESS_TOKEN', 'token'],
    ['PING_SECRET', SECRET],
    ['SIGNING_SEED_B64', seed.toString('base64')],
    ['OWNER_EMAIL', 'owner@example.com'],
  ]);
  const state = { sent: [], fetched: [], triggers: [], failMail };
  const context = {
    console: { error() {}, log() {} },
    Logger: { log() {} },
    Utilities: {
      DigestAlgorithm: { SHA_512: 'sha512', SHA_256: 'sha256' },
      computeDigest(algorithm, data) {
        const input = typeof data === 'string' ? Buffer.from(data) : Buffer.from(data.map((b) => b & 0xff));
        return signed(crypto.createHash(algorithm).update(input).digest());
      },
      getUuid: () => crypto.randomUUID(),
      base64Decode: (text) => signed(Buffer.from(text, 'base64')),
    },
    PropertiesService: {
      getScriptProperties: () => ({
        getProperty: (name) => (store.has(name) ? store.get(name) : null),
        setProperty: (name, value) => store.set(name, value),
        getKeys: () => [...store.keys()],
      }),
    },
    LockService: { getScriptLock: () => ({ waitLock() {}, releaseLock() {} }) },
    ContentService: { createTextOutput: (text) => ({ text }) },
    MailApp: {
      sendEmail(options) {
        if (state.failMail) throw new Error('mail is down');
        state.sent.push(options);
      },
    },
    UrlFetchApp: {
      fetch(url) {
        state.fetched.push(url);
        const id = decodeURIComponent(url.split('/sales/')[1]);
        const sale = sales[id];
        return {
          getResponseCode: () => (sale ? 200 : 404),
          getContentText: () => JSON.stringify(sale ? { success: true, sale } : { success: false }),
        };
      },
    },
    ScriptApp: {
      getProjectTriggers: () => state.triggers,
      newTrigger: (name) => ({
        timeBased: () => ({
          everyMinutes: () => ({ create: () => state.triggers.push({ getHandlerFunction: () => name }) }),
        }),
      }),
    },
  };
  vm.createContext(context);
  for (const file of ['Ed25519.gs', 'Code.gs']) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, file), 'utf8'), context, { filename: file });
  }
  return { context, state, store };
}

const sale = (overrides = {}) => ({
  id: 's1',
  email: 'buyer@example.com',
  product_name: 'VoxScribe Pro',
  refunded: false,
  ...overrides,
});
const ping = (context, params) => context.doPost({ parameter: { s: SECRET, sale_id: 's1', ...params } }).text;

if (process.argv[2] === '--emit-key') {
  const { context, store } = load({ seed: Buffer.from(process.argv[3], 'hex') });
  const props = context.PropertiesService.getScriptProperties();
  process.stdout.write(context.issueKey_(props));
  process.exit(0);
}

test('signing matches the RFC 8032 test vector', () => {
  const { context } = load();
  const seed = Buffer.from('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60', 'hex');
  const signature = Buffer.from(context.edSign([...seed], [])).toString('hex');
  assert.equal(
    signature,
    'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b',
  );
});

test('signing matches Node for random seeds and messages', () => {
  const { context } = load();
  for (let i = 0; i < 12; i++) {
    const seed = crypto.randomBytes(32);
    const message = crypto.randomBytes(1 + (i % 9) * 7);
    const expected = crypto
      .sign(null, message, { key: Buffer.concat([PKCS8_PREFIX, seed]), format: 'der', type: 'pkcs8' })
      .toString('hex');
    assert.equal(Buffer.from(context.edSign([...seed], [...message])).toString('hex'), expected);
  }
});

test('the self test passes in the sandbox', () => {
  const { context } = load();
  context.selfTest();
});

test('a paid Pro sale emails one key to the buyer', () => {
  const { context, state } = load({ sales: { s1: sale() } });

  assert.equal(ping(context, {}), 'sent');

  assert.equal(state.sent.length, 1);
  assert.equal(state.sent[0].to, 'buyer@example.com');
  assert.equal(state.sent[0].bcc, 'owner@example.com');
  assert.match(state.sent[0].body, /[A-Z2-7]{8}(-[A-Z2-7]{8}){13,14}/);
  assert.doesNotMatch(state.sent[0].body, new RegExp('[\\u2013\\u2014]'));
});

test('the email comes from the Gumroad record, not from the ping', () => {
  const { context, state } = load({ sales: { s1: sale() } });

  ping(context, { email: 'attacker@example.com' });

  assert.equal(state.sent[0].to, 'buyer@example.com');
});

test('a repeated ping does not send a second key', () => {
  const { context, state } = load({ sales: { s1: sale() } });

  ping(context, {});
  assert.equal(ping(context, {}), 'duplicate');

  assert.equal(state.sent.length, 1);
});

test('a wrong secret is ignored and never reaches Gumroad', () => {
  const { context, state } = load({ sales: { s1: sale() } });

  assert.equal(context.doPost({ parameter: { s: 'wrong', sale_id: 's1' } }).text, 'ignored');
  assert.equal(context.doPost({ parameter: { sale_id: 's1' } }).text, 'ignored');

  assert.equal(state.fetched.length, 0);
  assert.equal(state.sent.length, 0);
});

test('a ping for a sale Gumroad does not know is not trusted', () => {
  const { context, state } = load({ sales: {} });

  assert.equal(ping(context, { sale_id: 'fake' }), 'unverified');
  assert.equal(state.sent.length, 0);
});

test('refunded sales and other products get nothing', () => {
  const { context, state } = load({
    sales: { s1: sale({ refunded: true }), s2: sale({ id: 's2', product_name: 'Another Thing' }) },
  });

  assert.equal(ping(context, {}), 'refunded');
  assert.equal(ping(context, { sale_id: 's2' }), 'other product');
  assert.equal(state.sent.length, 0);
});

test('a failed email keeps the key and the retry sends the same one', () => {
  const { context, state, store } = load({ sales: { s1: sale() }, failMail: true });

  assert.equal(ping(context, {}), 'will retry');
  const savedKey = JSON.parse(store.get('sale:s1')).key;
  assert.equal(state.sent.length, 0);

  state.failMail = false;
  context.retryUndelivered();

  assert.equal(state.sent.length, 1);
  assert.ok(state.sent[0].body.includes(savedKey));
  assert.equal(JSON.parse(store.get('sale:s1')).delivered, true);
  assert.equal(ping(context, {}), 'duplicate');
});

test('setup starts the retry timer once', () => {
  const { context, state } = load();

  context.setup();
  context.setup();

  assert.equal(state.triggers.length, 1);
});

test('setup stops when a setting is missing', () => {
  const { context, store } = load();
  store.delete('PING_SECRET');

  assert.throws(() => context.setup(), /PING_SECRET/);
});
