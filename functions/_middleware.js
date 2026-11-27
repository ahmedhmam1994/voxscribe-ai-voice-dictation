// Cloudflare Pages middleware. docs/_routes.json sends only /api/* and /vercel.json here, so
// the rest of the site is served as plain files and never counts against the function quota.
//
// The Vercel copies of the API (docs/api/*.js) and docs/vercel.json sit in the same folder as
// the site, so without this they would be served as plain files. Vercel never served them.

export async function onRequest(context) {
  const path = new URL(context.request.url).pathname;
  if (path === "/vercel.json" || (path.startsWith("/api/") && path.endsWith(".js"))) {
    return new Response("Not found", { status: 404 });
  }
  return context.next();
}
