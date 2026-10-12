/**
 * Ed25519 signing (RFC 8032) with BigInt, and nothing else.
 *
 * Written out here instead of pasting a third-party library into a script that
 * holds the license signing key. SHA-512 comes from Apps Script's own
 * Utilities.computeDigest. Only signing is needed: the apps check keys, this
 * only makes them.
 *
 * Checked in tools/apps-script-fulfillment/test.js against the RFC 8032 test
 * vectors and against Python's cryptography library.
 */

const ED_P = (1n << 255n) - 19n;
const ED_L = (1n << 252n) + 27742317777372353535851937790883648493n;

function edMod(a, m) {
  const r = a % (m === undefined ? ED_P : m);
  return r >= 0n ? r : r + (m === undefined ? ED_P : m);
}

function edPow(base, exponent, modulus) {
  let result = 1n;
  let b = edMod(base, modulus);
  let e = exponent;
  while (e > 0n) {
    if (e & 1n) result = (result * b) % modulus;
    b = (b * b) % modulus;
    e >>= 1n;
  }
  return result;
}

function edInv(a) {
  return edPow(a, ED_P - 2n, ED_P);
}

const ED_D = edMod(-121665n * edInv(121666n));
const ED_SQRT_M1 = edPow(2n, (ED_P - 1n) / 4n, ED_P);

function edRecoverX(y, sign) {
  const x2 = edMod((y * y - 1n) * edInv(ED_D * y * y + 1n));
  let x = edPow(x2, (ED_P + 3n) / 8n, ED_P);
  if (edMod(x * x - x2) !== 0n) x = edMod(x * ED_SQRT_M1);
  if ((x & 1n) !== sign) x = ED_P - x;
  return x;
}

const ED_BASE_Y = edMod(4n * edInv(5n));
const ED_BASE_X = edRecoverX(ED_BASE_Y, 0n);
// Points are [X, Y, Z, T] in extended coordinates.
const ED_BASE = [ED_BASE_X, ED_BASE_Y, 1n, edMod(ED_BASE_X * ED_BASE_Y)];
const ED_IDENTITY = [0n, 1n, 1n, 0n];

function edAdd(p, q) {
  const a = edMod((p[1] - p[0]) * (q[1] - q[0]));
  const b = edMod((p[1] + p[0]) * (q[1] + q[0]));
  const c = edMod(p[3] * 2n * ED_D * q[3]);
  const d = edMod(p[2] * 2n * q[2]);
  const e = b - a;
  const f = d - c;
  const g = d + c;
  const h = b + a;
  return [edMod(e * f), edMod(g * h), edMod(f * g), edMod(e * h)];
}

function edMultiply(scalar, point) {
  let result = ED_IDENTITY;
  let addend = point;
  let s = scalar;
  while (s > 0n) {
    if (s & 1n) result = edAdd(result, addend);
    addend = edAdd(addend, addend);
    s >>= 1n;
  }
  return result;
}

function edEncode(point) {
  const zInv = edInv(point[2]);
  const x = edMod(point[0] * zInv);
  const y = edMod(point[1] * zInv);
  return edToBytes(y | ((x & 1n) << 255n), 32);
}

function edToBytes(value, length) {
  const bytes = new Array(length);
  let v = value;
  for (let i = 0; i < length; i++) {
    bytes[i] = Number(v & 0xffn);
    v >>= 8n;
  }
  return bytes;
}

function edFromBytes(bytes) {
  let value = 0n;
  for (let i = bytes.length - 1; i >= 0; i--) value = (value << 8n) | BigInt(bytes[i]);
  return value;
}

function edSha512(bytes) {
  // Apps Script wants signed bytes in and gives signed bytes back.
  const signed = bytes.map(function (b) { return b > 127 ? b - 256 : b; });
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_512, signed)
    .map(function (b) { return b & 0xff; });
}

/**
 * Signs `message` (array of bytes 0-255) with the 32 byte `seed`. Returns the
 * 64 byte signature as an array of bytes.
 */
function edSign(seed, message) {
  const hash = edSha512(seed);
  const clamped = hash.slice(0, 32);
  clamped[0] &= 248;
  clamped[31] &= 127;
  clamped[31] |= 64;
  const secret = edFromBytes(clamped);
  const prefix = hash.slice(32, 64);
  const publicKey = edEncode(edMultiply(secret, ED_BASE));
  const r = edMod(edFromBytes(edSha512(prefix.concat(message))), ED_L);
  const rPoint = edEncode(edMultiply(r, ED_BASE));
  const k = edMod(edFromBytes(edSha512(rPoint.concat(publicKey, message))), ED_L);
  const s = edMod(r + k * secret, ED_L);
  return rPoint.concat(edToBytes(s, 32));
}
