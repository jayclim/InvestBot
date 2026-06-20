// Lightweight, dependency-free request hardening for the public API routes.
//
// rateLimit() is a best-effort in-memory fixed-window limiter. It is per serverless
// instance (Vercel may run several), so it is not a global guarantee — but it pairs with
// the routes' CDN caching (identical requests are served from the edge and never invoke
// the function, so only cache-misses reach the limiter) and with strict input validation
// to make the endpoints impractical to spam or use as an open data proxy. For a hard
// global guarantee, back this with Vercel KV / Upstash.

const buckets = new Map(); // key -> { count, reset }

export function clientIp(request) {
  const xff = request.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return request.headers.get("x-real-ip") || "anon";
}

export function rateLimit(key, limit, windowMs) {
  const now = Date.now();
  let b = buckets.get(key);
  if (!b || now >= b.reset) { b = { count: 0, reset: now + windowMs }; buckets.set(key, b); }
  b.count += 1;
  if (buckets.size > 10000) { // opportunistic cleanup of expired entries
    for (const [k, v] of buckets) if (now >= v.reset) buckets.delete(k);
  }
  return { ok: b.count <= limit, retryAfter: Math.ceil((b.reset - now) / 1000) };
}

// A single ticker (1–7 chars: letters, optional dot/dash for class shares / some ETFs).
const TICKER = /^[A-Z][A-Z.-]{0,6}$/;
export const validSymbol = (s) => typeof s === "string" && TICKER.test(s);

export function tooMany(retryAfter) {
  return Response.json(
    { error: "rate_limited" },
    { status: 429, headers: { "Retry-After": String(retryAfter), "Cache-Control": "no-store" } }
  );
}

export function badRequest(msg) {
  return Response.json({ error: msg || "bad_request" }, { status: 400, headers: { "Cache-Control": "no-store" } });
}
