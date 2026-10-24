// Vercel serverless function: the optional "get one email when a big update
// ships" box on the home page.
//
// An address is kept only when the visitor types it in and presses the button.
// It is stored in Upstash Redis (the same store as activate.js) as a sorted
// set, with the sign-up time as the score. Nothing else is stored: no IP
// address, no browser details. The rate limit keeps only a salted hash of the
// IP address for one hour, so it cannot be turned back into an address.
//
// POST /api/subscribe  {"email": "..."}                  -> {"ok": true}
// POST /api/subscribe  {"email": "...", "remove": true}  -> {"ok": true}
//
// Needs UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN (already set for
// activate.js). Single opt-in: there is no mail server here to send a
// confirmation, so the form tells people exactly what happens.

const crypto = require("crypto");

const LIST_KEY = "subscribers";
const MAX_PER_HOUR = 5;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

async function upstash(command) {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error("storage is not configured");
  const response = await fetch(`${url}/${command.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data.result;
}

function cleanEmail(value) {
  if (typeof value !== "string") return null;
  const email = value.trim().toLowerCase();
  if (email.length < 6 || email.length > 254 || !EMAIL_PATTERN.test(email)) return null;
  return email;
}

function visitorKey(req) {
  const forwarded = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim();
  const hourStamp = Math.floor(Date.now() / 3600000);
  const salt = process.env.UPSTASH_REDIS_REST_TOKEN || "voxscribe";
  const hash = crypto.createHash("sha256").update(`${forwarded}|${hourStamp}|${salt}`).digest("hex");
  return `subscribe:rate:${hash.slice(0, 24)}`;
}

function reply(res, status, body) {
  res.status(status).setHeader("Cache-Control", "no-store").json(body);
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return reply(res, 405, { ok: false, error: "Use POST." });
  }

  const body = typeof req.body === "string" ? safeParse(req.body) : req.body || {};

  // Hidden field that people never see: only scripts fill it in. Pretend it worked.
  if (typeof body.website === "string" && body.website.trim() !== "") {
    return reply(res, 200, { ok: true });
  }

  const email = cleanEmail(body.email);
  if (!email) return reply(res, 400, { ok: false, error: "That does not look like an email address." });

  try {
    const key = visitorKey(req);
    const count = Number(await upstash(["incr", key]));
    if (count === 1) await upstash(["expire", key, "3600"]);
    if (count > MAX_PER_HOUR) {
      return reply(res, 429, { ok: false, error: "Too many tries. Please wait a while." });
    }

    if (body.remove === true) {
      await upstash(["zrem", LIST_KEY, email]);
    } else {
      await upstash(["zadd", LIST_KEY, "NX", String(Date.now()), email]);
    }
    return reply(res, 200, { ok: true });
  } catch {
    return reply(res, 500, { ok: false, error: "Something went wrong. Please try again later." });
  }
};

function safeParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

module.exports.cleanEmail = cleanEmail;
