// Cloudflare Pages middleware. docs/_routes.json sends only /api/* and /vercel.json here, so
// the rest of the site is served as plain files and never counts against the function quota.
//
// docs/vercel.json (kept so the old vercel.app hosts keep forwarding to voxscribe.dev) sits in
// the same folder as the site, so without this it would be served as a plain file.

export async function onRequest(context) {
  const path = new URL(context.request.url).pathname;
  if (path === "/vercel.json" || (path.startsWith("/api/") && path.endsWith(".js"))) {
    return new Response("Not found", { status: 404 });
  }
  return context.next();
}
