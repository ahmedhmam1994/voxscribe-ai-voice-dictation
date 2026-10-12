/**
 * Ed25519 signing (RFC 8032), and nothing else, with plain numbers (no BigInt, which
 * Apps Script's parser rejects).
 *
 * The field arithmetic follows TweetNaCl's well known layout: a number is 16 limbs
 * of 16 bits. It is written out here instead of pasting a library into a script that
 * holds the license signing key. SHA-512 comes from Apps Script's own
 * Utilities.computeDigest. Only signing is needed: the apps check keys, this only
 * makes them.
 *
 * Checked in tools/apps-script-fulfillment/test.js against the RFC 8032 test vector
 * and against Node's own Ed25519 on random inputs.
 */

function edGf(init) {
  var r = new Float64Array(16);
  if (init) for (var i = 0; i < init.length; i++) r[i] = init[i];
  return r;
}

var ED_GF0 = edGf();
var ED_GF1 = edGf([1]);
var ED_D2 = edGf([
  0xf159, 0x26b2, 0x9b94, 0xebd6, 0xb156, 0x8283, 0x149a, 0x00e0,
  0xd130, 0xeef3, 0x80f2, 0x198e, 0xfce7, 0x56df, 0xd9dc, 0x2406,
]);
var ED_X = edGf([
  0xd51a, 0x8f25, 0x2d60, 0xc956, 0xa7b2, 0x9525, 0xc760, 0x692c,
  0xdc5c, 0xfdd6, 0xe231, 0xc0a4, 0x53fe, 0xcd6e, 0x36d3, 0x2169,
]);
var ED_Y = edGf([
  0x6658, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666,
  0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666, 0x6666,
]);
var ED_L = new Float64Array([
  0xed, 0xd3, 0xf5, 0x5c, 0x1a, 0x63, 0x12, 0x58, 0xd6, 0x9c, 0xf7, 0xa2, 0xde, 0xf9, 0xde, 0x14,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x10,
]);

function edSet(o, a) {
  for (var i = 0; i < 16; i++) o[i] = a[i];
}

function edCarry(o) {
  var c = 1;
  for (var i = 0; i < 16; i++) {
    var v = o[i] + c + 65535;
    c = Math.floor(v / 65536);
    o[i] = v - c * 65536;
  }
  o[0] += c - 1 + 37 * (c - 1);
}

function edSelect(p, q, b) {
  var c = ~(b - 1);
  for (var i = 0; i < 16; i++) {
    var t = c & (p[i] ^ q[i]);
    p[i] ^= t;
    q[i] ^= t;
  }
}

function edPack25519(o, n) {
  var i, j, b;
  var m = edGf();
  var t = edGf();
  for (i = 0; i < 16; i++) t[i] = n[i];
  edCarry(t);
  edCarry(t);
  edCarry(t);
  for (j = 0; j < 2; j++) {
    m[0] = t[0] - 0xffed;
    for (i = 1; i < 15; i++) {
      m[i] = t[i] - 0xffff - ((m[i - 1] >> 16) & 1);
      m[i - 1] &= 0xffff;
    }
    m[15] = t[15] - 0x7fff - ((m[14] >> 16) & 1);
    b = (m[15] >> 16) & 1;
    m[14] &= 0xffff;
    edSelect(t, m, 1 - b);
  }
  for (i = 0; i < 16; i++) {
    o[2 * i] = t[i] & 0xff;
    o[2 * i + 1] = t[i] >> 8;
  }
}

function edParity(a) {
  var d = new Array(32);
  edPack25519(d, a);
  return d[0] & 1;
}

function edAddField(o, a, b) {
  for (var i = 0; i < 16; i++) o[i] = a[i] + b[i];
}

function edSubField(o, a, b) {
  for (var i = 0; i < 16; i++) o[i] = a[i] - b[i];
}

function edMul(o, a, b) {
  var t = new Float64Array(31);
  var i, j;
  for (i = 0; i < 16; i++) {
    for (j = 0; j < 16; j++) t[i + j] += a[i] * b[j];
  }
  for (i = 0; i < 15; i++) t[i] += 38 * t[i + 16];
  for (i = 0; i < 16; i++) o[i] = t[i];
  edCarry(o);
  edCarry(o);
}

function edSquare(o, a) {
  edMul(o, a, a);
}

function edInvert(o, input) {
  var c = edGf();
  var a;
  for (a = 0; a < 16; a++) c[a] = input[a];
  for (a = 253; a >= 0; a--) {
    edSquare(c, c);
    if (a !== 2 && a !== 4) edMul(c, c, input);
  }
  for (a = 0; a < 16; a++) o[a] = c[a];
}

// Points are four field elements [X, Y, Z, T] in extended coordinates.
function edPointAdd(p, q) {
  var a = edGf(), b = edGf(), c = edGf(), d = edGf();
  var e = edGf(), f = edGf(), g = edGf(), h = edGf(), t = edGf();
  edSubField(a, p[1], p[0]);
  edSubField(t, q[1], q[0]);
  edMul(a, a, t);
  edAddField(b, p[0], p[1]);
  edAddField(t, q[0], q[1]);
  edMul(b, b, t);
  edMul(c, p[3], q[3]);
  edMul(c, c, ED_D2);
  edMul(d, p[2], q[2]);
  edAddField(d, d, d);
  edSubField(e, b, a);
  edSubField(f, d, c);
  edAddField(g, d, c);
  edAddField(h, b, a);
  edMul(p[0], e, f);
  edMul(p[1], h, g);
  edMul(p[2], g, f);
  edMul(p[3], e, h);
}

function edConditionalSwap(p, q, b) {
  for (var i = 0; i < 4; i++) edSelect(p[i], q[i], b);
}

function edEncode(r, p) {
  var tx = edGf(), ty = edGf(), zi = edGf();
  edInvert(zi, p[2]);
  edMul(tx, p[0], zi);
  edMul(ty, p[1], zi);
  edPack25519(r, ty);
  r[31] ^= edParity(tx) << 7;
}

function edScalarMult(p, q, s) {
  edSet(p[0], ED_GF0);
  edSet(p[1], ED_GF1);
  edSet(p[2], ED_GF1);
  edSet(p[3], ED_GF0);
  for (var i = 255; i >= 0; --i) {
    var b = (s[(i / 8) | 0] >> (i & 7)) & 1;
    edConditionalSwap(p, q, b);
    edPointAdd(q, p);
    edPointAdd(p, p);
    edConditionalSwap(p, q, b);
  }
}

function edScalarBase(p, s) {
  var q = [edGf(), edGf(), edGf(), edGf()];
  edSet(q[0], ED_X);
  edSet(q[1], ED_Y);
  edSet(q[2], ED_GF1);
  edMul(q[3], ED_X, ED_Y);
  edScalarMult(p, q, s);
}

// Reduces the 64 entry number x modulo the group order L into r (32 bytes).
function edModL(r, x) {
  var carry, i, j, k;
  for (i = 63; i >= 32; --i) {
    carry = 0;
    for (j = i - 32, k = i - 12; j < k; ++j) {
      x[j] += carry - 16 * x[i] * ED_L[j - (i - 32)];
      carry = Math.floor((x[j] + 128) / 256);
      x[j] -= carry * 256;
    }
    x[j] += carry;
    x[i] = 0;
  }
  carry = 0;
  for (j = 0; j < 32; j++) {
    x[j] += carry - (x[31] >> 4) * ED_L[j];
    carry = x[j] >> 8;
    x[j] &= 255;
  }
  for (j = 0; j < 32; j++) x[j] -= carry * ED_L[j];
  for (i = 0; i < 32; i++) {
    x[i + 1] += x[i] >> 8;
    r[i] = x[i] & 255;
  }
}

function edReduce(bytes64) {
  var x = new Float64Array(64);
  var i;
  for (i = 0; i < 64; i++) x[i] = bytes64[i];
  var out = new Array(64);
  for (i = 0; i < 64; i++) out[i] = 0;
  edModL(out, x);
  return out;
}

function edSha512(bytes) {
  // Apps Script wants signed bytes in and gives signed bytes back.
  var signed = bytes.map(function (b) { return b > 127 ? b - 256 : b; });
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_512, signed)
    .map(function (b) { return b & 0xff; });
}

/**
 * Signs `message` (array of bytes 0-255) with the 32 byte `seed`. Returns the
 * 64 byte signature as an array of bytes.
 */
function edSign(seed, message) {
  var d = edSha512(seed);
  d[0] &= 248;
  d[31] &= 127;
  d[31] |= 64;
  var i, j;

  var p = [edGf(), edGf(), edGf(), edGf()];
  edScalarBase(p, d);
  var publicKey = new Array(32);
  edEncode(publicKey, p);

  var r = edReduce(edSha512(d.slice(32, 64).concat(message)));
  edScalarBase(p, r);
  var rEncoded = new Array(32);
  edEncode(rEncoded, p);

  var h = edReduce(edSha512(rEncoded.concat(publicKey, message)));
  var x = new Float64Array(64);
  for (i = 0; i < 32; i++) x[i] = r[i];
  for (i = 0; i < 32; i++) {
    for (j = 0; j < 32; j++) x[i + j] += h[i] * d[j];
  }
  var s = new Array(32);
  edModL(s, x);
  return rEncoded.concat(s);
}
