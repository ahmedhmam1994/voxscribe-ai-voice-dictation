/**
 * Emails a VoxScribe Pro license key within seconds of a Gumroad sale.
 *
 * Gumroad calls this web app (its "Ping") on every sale. The script then:
 *   1. checks the secret in the address, so a stranger cannot trigger it;
 *   2. asks Gumroad's API about that sale, so a faked ping cannot mint a key;
 *   3. skips anything that is not a paid VoxScribe Pro sale, or already handled;
 *   4. signs a license key and emails it to the buyer from this Google account.
 *
 * Setup is in README.md. Secrets live in Script Properties (Project Settings),
 * never in this file:
 *   GUMROAD_ACCESS_TOKEN  Gumroad access token (view_sales)
 *   PING_SECRET           a long random string, also put in the Ping address
 *   SIGNING_SEED_B64      the license signing key, base64
 *   OWNER_EMAIL           optional, gets a copy of every email sent
 */

const PRODUCT_NAME = 'VoxScribe Pro';
const RELEASES_URL = 'https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation/releases';
const SALE_PREFIX = 'sale:';
const SIGNATURE_BYTES = 64;
const LICENSE_ID_BYTES = 8;

// ---- entry points ---------------------------------------------------------

function doGet() {
  return reply_('VoxScribe fulfillment is running.');
}

function doPost(e) {
  const props = PropertiesService.getScriptProperties();
  const params = (e && e.parameter) || {};
  if (!sameText_(params.s || '', props.getProperty('PING_SECRET') || '')) {
    return reply_('ignored');
  }
  const saleId = String(params.sale_id || '').trim();
  if (!saleId) return reply_('no sale id');

  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    return reply_(handleSale_(saleId, props));
  } finally {
    lock.releaseLock();
  }
}

/** Runs on a timer: emails any key that could not be sent the first time. */
function retryUndelivered() {
  const props = PropertiesService.getScriptProperties();
  const lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    props.getKeys().filter(function (k) { return k.indexOf(SALE_PREFIX) === 0; }).forEach(function (k) {
      const entry = JSON.parse(props.getProperty(k));
      if (!entry.delivered) deliver_(k, entry, props);
    });
  } finally {
    lock.releaseLock();
  }
}

/** Run once from the editor: checks the settings and starts the retry timer. */
function setup() {
  ['GUMROAD_ACCESS_TOKEN', 'PING_SECRET', 'SIGNING_SEED_B64'].forEach(function (name) {
    if (!PropertiesService.getScriptProperties().getProperty(name)) {
      throw new Error('Missing script property: ' + name);
    }
  });
  const has = ScriptApp.getProjectTriggers().some(function (t) {
    return t.getHandlerFunction() === 'retryUndelivered';
  });
  if (!has) ScriptApp.newTrigger('retryUndelivered').timeBased().everyMinutes(10).create();
  selfTest();
  Logger.log('Setup is complete.');
}

/** Run from the editor to prove the signing code works in Google's runtime. */
function selfTest() {
  // RFC 8032 test vector 1: seed 9d61...7f60 signs the empty message.
  const seed = hexToBytes_('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60');
  const expected = 'e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b';
  if (bytesToHex_(edSign(seed, [])) !== expected) throw new Error('Signing self test failed.');
  Logger.log('Signing self test passed.');
}

// ---- sale handling --------------------------------------------------------

function handleSale_(saleId, props) {
  const stateKey = SALE_PREFIX + saleId;
  const existing = props.getProperty(stateKey);
  if (existing) {
    const entry = JSON.parse(existing);
    if (entry.delivered) return 'duplicate';
    return deliver_(stateKey, entry, props) ? 'resent' : 'will retry';
  }

  const sale = fetchSale_(saleId, props.getProperty('GUMROAD_ACCESS_TOKEN'));
  if (!sale) return 'unverified';
  if (String(sale.product_name || '').toLowerCase().indexOf(PRODUCT_NAME.toLowerCase()) < 0) {
    return 'other product';
  }
  if (sale.refunded || sale.chargedback || sale.disputed) return 'refunded';
  if (!sale.email) return 'no email';

  const entry = { email: String(sale.email).trim(), key: issueKey_(props), delivered: false, at: new Date().toISOString() };
  // Saved before emailing, so a failed email is retried with the same key.
  props.setProperty(stateKey, JSON.stringify(entry));
  return deliver_(stateKey, entry, props) ? 'sent' : 'will retry';
}

function fetchSale_(saleId, token) {
  const response = UrlFetchApp.fetch('https://api.gumroad.com/v2/sales/' + encodeURIComponent(saleId), {
    headers: { Authorization: 'Bearer ' + token },
    muteHttpExceptions: true,
  });
  if (response.getResponseCode() !== 200) return null;
  const data = JSON.parse(response.getContentText());
  return data && data.success ? data.sale : null;
}

function deliver_(stateKey, entry, props) {
  try {
    const mail = composeEmail_(entry.key);
    const options = { to: entry.email, subject: mail.subject, body: mail.body, name: 'Ahmed' };
    const owner = props.getProperty('OWNER_EMAIL');
    if (owner) {
      options.bcc = owner;
      options.replyTo = owner;
    }
    MailApp.sendEmail(options);
    entry.delivered = true;
    props.setProperty(stateKey, JSON.stringify(entry));
    return true;
  } catch (error) {
    console.error('Email failed for ' + stateKey + ': ' + error);
    return false;
  }
}

function composeEmail_(key) {
  return {
    subject: 'Your VoxScribe Pro license key',
    body: [
      'Hi,',
      '',
      'Thanks for buying VoxScribe Pro. Here is your license key:',
      '',
      key,
      '',
      'To unlock it on Windows: open VoxScribe, go to Settings, find the license section near the top, paste the key and click Unlock. It needs an internet connection that one time, and after that Pro works offline.',
      '',
      'The same key also works on the Android app (one Windows PC and one Android phone). On the phone, open the app, go to Settings, then VoxScribe Pro, and paste it there. The Android app is a separate download on the releases page: ' + RELEASES_URL,
      '',
      'If it says the key is already activated, or anything else looks wrong, just reply to this email and I will sort it out.',
      '',
      'Thanks again for supporting it.',
      '',
      'Ahmed',
      '',
    ].join('\n'),
  };
}

// ---- keys -----------------------------------------------------------------

/** A license key in the same format the apps check: base32(id + signature), in blocks of 8. */
function issueKey_(props) {
  const seed = base64ToBytes_(props.getProperty('SIGNING_SEED_B64'));
  const idSource = Utilities.getUuid() + Date.now() + Math.random();
  const licenseId = edSha256_(idSource).slice(0, LICENSE_ID_BYTES);
  const signature = edSign(seed, licenseId);
  return formatKey_(licenseId.concat(signature));
}

function formatKey_(bytes) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = 0;
  let buffer = 0;
  let out = '';
  bytes.forEach(function (byte) {
    buffer = (buffer << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      bits -= 5;
      out += alphabet[(buffer >> bits) & 31];
    }
    buffer &= (1 << bits) - 1;
  });
  if (bits > 0) out += alphabet[(buffer << (5 - bits)) & 31];
  return out.match(/.{1,8}/g).join('-');
}

// ---- small helpers --------------------------------------------------------

function edSha256_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text)
    .map(function (b) { return b & 0xff; });
}

function base64ToBytes_(text) {
  return Utilities.base64Decode(text).map(function (b) { return b & 0xff; });
}

function hexToBytes_(hex) {
  const bytes = [];
  for (let i = 0; i < hex.length; i += 2) bytes.push(parseInt(hex.substr(i, 2), 16));
  return bytes;
}

function bytesToHex_(bytes) {
  return bytes.map(function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
}

function sameText_(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i++) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
}

function reply_(text) {
  return ContentService.createTextOutput(text);
}
