// Serverless route: live quotes from Finnhub.
// GET /api/quotes?symbols=NVDA,AMD  ->  { quotes: { NVDA: {price,change,pct,prevClose,t} }, asOf }
// FINNHUB_API_KEY is a Vercel env var, never sent to the client. CDN-cached 30s.

import { clientIp, rateLimit, validSymbol, tooMany } from "../../../lib/ratelimit";

export const dynamic = "force-dynamic";
export const maxDuration = 10;

export async function GET(request) {
  const rl = rateLimit("quotes:" + clientIp(request), 20, 60000);
  if (!rl.ok) return tooMany(rl.retryAfter);

  const key = process.env.FINNHUB_API_KEY;
  if (!key) {
    return Response.json({ error: "FINNHUB_API_KEY not set" }, { status: 500 });
  }

  const { searchParams } = new URL(request.url);
  const symbols = String(searchParams.get("symbols") || "")
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(validSymbol)
    .slice(0, 30); // bound fan-out (Finnhub free = 60 calls/min)

  const quotes = {};
  await Promise.all(
    symbols.map(async (sym) => {
      try {
        const r = await fetch(
          `https://finnhub.io/api/v1/quote?symbol=${encodeURIComponent(sym)}&token=${key}`,
          { cache: "no-store", signal: AbortSignal.timeout(5000) }
        );
        if (!r.ok) return;
        const j = await r.json();
        if (j && typeof j.c === "number" && j.c > 0) {
          quotes[sym] = { price: j.c, change: j.d, pct: j.dp, prevClose: j.pc, t: j.t };
        }
      } catch (_e) {
        /* skip symbol */
      }
    })
  );

  return Response.json(
    { quotes, asOf: Date.now() },
    { headers: { "Cache-Control": "s-maxage=30, stale-while-revalidate=30" } }
  );
}
