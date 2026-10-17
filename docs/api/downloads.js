// Vercel serverless function: the README's downloads badge, drawn here
// instead of by shields.io, whose shared GitHub quota sometimes runs out and
// leaves the badge reading "invalid".
//
// Total = every asset download across all releases (Windows and Android).
// The last good total is kept in Upstash Redis (same store as activate.js),
// so a GitHub hiccup shows that number instead of an error. The CDN caches
// the badge for an hour, so GitHub is asked at most about once an hour.
//
// GET /api/downloads        -> SVG badge
// GET /api/downloads?json=1 -> {"downloads": 204}

const REPO = "ahmedhmam1994/voxscribe-ai-voice-dictation";
const CACHE_KEY = "badge:downloads";

async function upstash(command) {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  const response = await fetch(`${url}/${command.map(encodeURIComponent).join("/")}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await response.json();
  return data.error ? null : data.result;
}

async function countFromGitHub() {
  const headers = { Accept: "application/vnd.github+json", "User-Agent": "voxscribe-badge" };
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  let total = 0;
  for (let page = 1; page <= 10; page++) {
    const response = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=100&page=${page}`, { headers });
    if (!response.ok) throw new Error(`GitHub answered ${response.status}`);
    const releases = await response.json();
    for (const release of releases) {
      for (const asset of release.assets || []) total += asset.download_count || 0;
    }
    if (releases.length < 100) break;
  }
  return total;
}

function formatCount(n) {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
  if (n >= 1e4) return `${(n / 1e3).toFixed(1).replace(/\.0$/, "")}k`;
  return String(n);
}

// Flat badge in the shields.io style, so it sits well next to the others.
function badge(label, value, color) {
  const charWidth = (s) => Math.round(s.length * 6.6 + 10);
  const lw = charWidth(label);
  const vw = charWidth(value);
  const w = lw + vw;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="20" role="img" aria-label="${label}: ${value}">
<title>${label}: ${value}</title>
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="${w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="${lw}" height="20" fill="#555"/><rect x="${lw}" width="${vw}" height="20" fill="${color}"/><rect width="${w}" height="20" fill="url(#s)"/></g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="${lw / 2}" y="15" fill="#010101" fill-opacity=".3">${label}</text><text x="${lw / 2}" y="14">${label}</text>
<text x="${lw + vw / 2}" y="15" fill="#010101" fill-opacity=".3">${value}</text><text x="${lw + vw / 2}" y="14">${value}</text>
</g></svg>`;
}

module.exports = async (req, res) => {
  let total = null;
  try {
    total = await countFromGitHub();
    await upstash(["set", CACHE_KEY, String(total)]).catch(() => null);
  } catch {
    const saved = await upstash(["get", CACHE_KEY]).catch(() => null);
    total = saved === null ? null : Number(saved);
  }

  // An hour at the CDN, and a stale copy for up to a week if a refresh fails.
  res.setHeader("Cache-Control", "public, max-age=3600, s-maxage=3600, stale-while-revalidate=604800, stale-if-error=604800");

  if (req.query && req.query.json) {
    res.status(200).json({ downloads: total });
    return;
  }
  res.setHeader("Content-Type", "image/svg+xml; charset=utf-8");
  const value = total === null ? "see releases" : formatCount(total);
  res.status(200).send(badge("downloads", value, total === null ? "#9f9f9f" : "#007ec6"));
};
