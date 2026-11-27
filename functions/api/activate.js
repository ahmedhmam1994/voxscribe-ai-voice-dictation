// Cloudflare Pages Function: checks/claims a VoxScribe Pro license key against a hardware id,
// so a key can't just be typed into an unlimited number of machines. Same behaviour as
// docs/api/activate.js, the Vercel copy, which installed apps still call at
// getvoxscribe.vercel.app/api/activate and which must keep running for them.
// Day-to-day Pro checks (core/license.py's is_pro()) stay fully offline; this only runs once,
// when the user clicks Unlock.
//
// Storage: Upstash Redis (REST API), the same database as the Vercel copy, so both see the
// same slots. Needs UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN in the Pages settings.
//
// One key unlocks two Windows PCs and two Android phones: each platform has its own slots.
// action "deactivate" frees this device's slot, so a key can move to a new PC or phone.
//
// Verifies the key's Ed25519 signature itself (same public key as core/license.py) rather than
// trusting the client.

const PUBLIC_KEY_HEX = "3c99649247537fb1a3ecd9e7ba0987ee1c3bdae92b911dae9eeb58095b3e2edc";
const LICENSE_ID_LEN = 8;
const SIGNATURE_LEN = 64;

// RFC 4648 base32, the alphabet Python's base64.b32decode uses, so keys made by
// scripts/generate_license_key.py decode the same here.
const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function base32Decode(input) {
  const clean = input.toUpperCase().replace(/[^A-Z2-7]/g, "");
  let bits = "";
  for (const char of clean) {
    const value = BASE32_ALPHABET.indexOf(char);
    if (value === -1) throw new Error("invalid base32 character");
    bits += value.toString(2).padStart(5, "0");
  }
  const bytes = new Uint8Array(Math.floor(bits.length / 8));
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(bits.slice(i * 8, i * 8 + 8), 2);
  return bytes;
}

function hexBytes(hex) {
  return new Uint8Array(hex.match(/../g).map((h) => parseInt(h, 16)));
}

function toHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

let publicKeyPromise = null;
function publicKey() {
  if (!publicKeyPromise) {
    publicKeyPromise = crypto.subtle.importKey("raw", hexBytes(PUBLIC_KEY_HEX), { name: "Ed25519" }, false, ["verify"]);
  }
  return publicKeyPromise;
}

// Returns the license id as hex, or null if the key isn't validly signed.
export async function verifyLicenseKey(key) {
  if (typeof key !== "string") return null;
  const cleaned = key.trim().replace(/[- ]/g, "").toUpperCase();
  let raw;
  try {
    raw = base32Decode(cleaned);
  } catch {
    return null;
  }
  if (raw.length !== LICENSE_ID_LEN + SIGNATURE_LEN) return null;

  const licenseId = raw.subarray(0, LICENSE_ID_LEN);
  const signature = raw.subarray(LICENSE_ID_LEN);
  const valid = await crypto.subtle.verify({ name: "Ed25519" }, await publicKey(), signature, licenseId);
  return valid ? toHex(licenseId) : null;
}

// Redis script: delete KEYS[1] only if it holds ARGV[1]. Returns 1 or 0.
const RELEASE_IF_OWNER =
  "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end";

async function upstash(env, command) {
  const url = env.UPSTASH_REDIS_REST_URL;
  const token = env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error("activation storage is not configured");

  const response = await fetch(`${url}/${command.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data.result;
}

function reply(status, body) {
  return Response.json(body, { status });
}

export async function onRequest({ request, env }) {
  if (request.method !== "POST") return reply(405, { ok: false, message: "Method not allowed." });

  let body;
  try {
    body = JSON.parse(await request.text());
  } catch {
    body = {};
  }
  const { key, hardware_id: hardwareId, platform, action } = body || {};

  const licenseId = await verifyLicenseKey(key);
  if (!licenseId) return reply(400, { ok: false, message: "That key isn't valid." });
  const safeHardwareId = (hardwareId || "unknown").toString().slice(0, 128);

  // Windows keeps the original key name for its first slot so existing
  // activations still match; each platform's second slot adds ":2".
  const base = platform === "android" ? `license:${licenseId}:android` : `license:${licenseId}`;
  const slots = [base, `${base}:2`];
  try {
    if (action === "deactivate") {
      // Deletes a slot only if this device holds it (compare and delete in
      // one step), so one device can never free another device's slot.
      let freed = 0;
      for (const slot of slots) {
        freed += Number(await upstash(env, ["eval", RELEASE_IF_OWNER, "1", slot, safeHardwareId]));
      }
      return reply(200, { ok: true, message: freed ? "deactivated" : "not_active_here" });
    }

    const holders = await Promise.all(slots.map((slot) => upstash(env, ["get", slot])));
    if (holders.includes(safeHardwareId)) return reply(200, { ok: true, message: "already_this_device" });

    // SET ... NX claims a slot only if nobody holds it, in one step, so two
    // devices activating at the same moment can't both win the same slot.
    for (const slot of slots) {
      if ((await upstash(env, ["set", slot, safeHardwareId, "NX"])) === "OK") {
        return reply(200, { ok: true, message: "activated" });
      }
    }
    const where = platform === "android" ? "phones" : "PCs";
    return reply(409, {
      ok: false,
      message:
        `This key is already active on two ${where}. Open VoxScribe on one of them ` +
        "and choose Remove license to free a slot, then try again.",
    });
  } catch (exc) {
    // The details go to the Pages log only; the app just needs to know it failed.
    console.error("activation failed:", exc);
    return reply(500, { ok: false, message: "Activation server error. Please try again later." });
  }
}
