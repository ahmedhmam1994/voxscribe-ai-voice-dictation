// Vercel serverless function: checks/claims a VoxScribe Pro license key
// against a hardware id, so a key can't just be typed into an unlimited
// number of machines. This is the one server VoxScribe's licensing ever
// talks to -- day-to-day Pro checks (core/license.py's is_pro()) stay
// fully offline; this only runs once, when the user clicks Unlock.
//
// Storage: Upstash Redis (REST API, no driver/connection pooling needed
// in a serverless function). Needs UPSTASH_REDIS_REST_URL and
// UPSTASH_REDIS_REST_TOKEN set as Vercel project env vars.
//
// One key unlocks one Windows PC and one Android phone: each platform
// claims its own slot, so activating on the phone never collides with the PC.
//
// Verifies the key's Ed25519 signature itself (same public key as
// core/license.py) rather than trusting the client -- a request claiming
// to hold a valid key still has to actually have one.

const PUBLIC_KEY_HEX = "3c99649247537fb1a3ecd9e7ba0987ee1c3bdae92b911dae9eeb58095b3e2edc";
const LICENSE_ID_LEN = 8;
const SIGNATURE_LEN = 64;

const crypto = require("crypto");

// Node has no built-in base32 (RFC 4648) codec -- Python's base64.b32decode
// uses this same alphabet, so this has to match exactly for keys generated
// by scripts/generate_license_key.py to decode correctly here.
const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function base32Decode(input) {
  const clean = input.toUpperCase().replace(/[^A-Z2-7]/g, "");
  let bits = "";
  for (const char of clean) {
    const value = BASE32_ALPHABET.indexOf(char);
    if (value === -1) throw new Error("invalid base32 character");
    bits += value.toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return Buffer.from(bytes);
}

function ed25519PublicKeyFromRaw(hex) {
  // SPKI DER wrapper for a raw 32-byte Ed25519 public key -- the
  // "302a300506032b6570032100" prefix is the fixed ASN.1 header for the
  // Ed25519 OID (1.3.101.112), constant regardless of the key itself.
  const der = Buffer.from("302a300506032b6570032100" + hex, "hex");
  return crypto.createPublicKey({ key: der, format: "der", type: "spki" });
}

function verifyLicenseKey(key) {
  const cleaned = (key || "").trim().replace(/[- ]/g, "").toUpperCase();
  let raw;
  try {
    raw = base32Decode(cleaned);
  } catch {
    return null;
  }
  if (raw.length !== LICENSE_ID_LEN + SIGNATURE_LEN) return null;

  const licenseId = raw.subarray(0, LICENSE_ID_LEN);
  const signature = raw.subarray(LICENSE_ID_LEN);
  const publicKey = ed25519PublicKeyFromRaw(PUBLIC_KEY_HEX);
  const valid = crypto.verify(null, licenseId, publicKey, signature);
  return valid ? licenseId.toString("hex") : null;
}

async function upstash(command) {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error("activation storage is not configured");

  const response = await fetch(`${url}/${command.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data.result;
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, message: "Method not allowed." });
    return;
  }

  let body = req.body;
  if (typeof body === "string") {
    try {
      body = JSON.parse(body);
    } catch {
      body = {};
    }
  }
  const { key, hardware_id: hardwareId, platform } = body || {};

  const licenseId = verifyLicenseKey(key);
  if (!licenseId) {
    res.status(400).json({ ok: false, message: "That key isn't valid." });
    return;
  }
  const safeHardwareId = (hardwareId || "unknown").toString().slice(0, 128);

  // Windows keeps the original key name so existing activations still match.
  const redisKey = platform === "android" ? `license:${licenseId}:android` : `license:${licenseId}`;
  try {
    const existing = await upstash(["get", redisKey]);
    if (existing === null) {
      await upstash(["set", redisKey, safeHardwareId]);
      res.status(200).json({ ok: true, message: "activated" });
      return;
    }
    if (existing === safeHardwareId) {
      res.status(200).json({ ok: true, message: "already_this_device" });
      return;
    }
    res.status(409).json({
      ok: false,
      message: "This key is already activated on a different device.",
    });
  } catch (exc) {
    res.status(500).json({ ok: false, message: `Activation server error: ${exc.message}` });
  }
};
