// Cloudflare Pages Function: the optional "get one email when a big update ships or the price
// changes" box on the home page.
//
// An address is kept only when the visitor types it in and presses the button. It is stored in
// Upstash Redis as a sorted set, with the sign-up time as the score. Nothing else is stored: no
// IP address, no browser details. The rate limit keeps only a salted hash of the IP address for
// one hour, so it cannot be turned back into an address.
//
// POST /api/subscribe  {"email": "..."}                  -> {"ok": true}
// POST /api/subscribe  {"email": "...", "remove": true}  -> {"ok": true}
//
// Needs UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN in the Pages project settings.

const LIST_KEY = "subscribers";
const MAX_PER_HOUR = 5;
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

async function upstash(env, command) {
  const url = env.UPSTASH_REDIS_REST_URL;
  const token = env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) throw new Error("storage is not configured");
  const response = await fetch(`${url}/${command.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await response.json();
  if (data.error) throw new Error(data.error);
  return data.result;
}

export function cleanEmail(value) {
  if (typeof value !== "string") return null;
  const email = value.trim().toLowerCase();
  if (email.length < 6 || email.length > 254 || !EMAIL_PATTERN.test(email)) return null;
  return email;
}

async function visitorKey(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "";
  const hourStamp = Math.floor(Date.now() / 3600000);
  const salt = env.UPSTASH_REDIS_REST_TOKEN || "voxscribe";
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${ip}|${hourStamp}|${salt}`));
  const hex = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `subscribe:rate:${hex.slice(0, 24)}`;
}

function reply(status, body, extra = {}) {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store", ...extra } });
}

async function readJson(request) {
  try {
    const body = JSON.parse(await request.text());
    return body && typeof body === "object" ? body : {};
  } catch {
    return {};
  }
}

export async function onRequest({ request, env }) {
  if (request.method !== "POST") return reply(405, { ok: false, error: "Use POST." }, { Allow: "POST" });

  const body = await readJson(request);

  // Hidden field that people never see: only scripts fill it in. Pretend it worked.
  if (typeof body.website === "string" && body.website.trim() !== "") return reply(200, { ok: true });

  const email = cleanEmail(body.email);
  if (!email) return reply(400, { ok: false, error: "That does not look like an email address." });

  try {
    const key = await visitorKey(request, env);
    const count = Number(await upstash(env, ["incr", key]));
    if (count === 1) await upstash(env, ["expire", key, "3600"]);
    if (count > MAX_PER_HOUR) return reply(429, { ok: false, error: "Too many tries. Please wait a while." });

    if (body.remove === true) {
      await upstash(env, ["zrem", LIST_KEY, email]);
    } else {
      await upstash(env, ["zadd", LIST_KEY, "NX", String(Date.now()), email]);
    }
    return reply(200, { ok: true });
  } catch {
    return reply(500, { ok: false, error: "Something went wrong. Please try again later." });
  }
}
