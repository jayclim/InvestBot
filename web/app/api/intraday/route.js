// Serverless route: intraday candles (incl. pre/after-hours) from Yahoo's chart API.
// GET /api/intraday?symbol=NVDA&range=1d|5d  ->  { symbol, range, candles:[{t,c,ext}], asOf }
// `ext` = true when the bar is outside the regular session (pre-market / after-hours).
// No API key. Unofficial endpoint — degrades to an empty list on any error.

import { clientIp, rateLimit, validSymbol, tooMany, badRequest } from "../../../lib/ratelimit";

export const dynamic = "force-dynamic";
export const maxDuration = 10;

const CFG = {
  "1d": { interval: "2m", range: "1d" },
  "5d": { interval: "5m", range: "5d" },
};

export async function GET(request) {
  const rl = rateLimit("intraday:" + clientIp(request), 30, 60000);
  if (!rl.ok) return tooMany(rl.retryAfter);

  const { searchParams } = new URL(request.url);
  const symbol = String(searchParams.get("symbol") || "").trim().toUpperCase();
  const rk = String(searchParams.get("range") || "1d");
  if (!validSymbol(symbol)) return badRequest("invalid symbol");
  if (!CFG[rk]) return badRequest("invalid range");
  const cfg = CFG[rk];

  let candles = [];
  try {
    const url =
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}` +
      `?interval=${cfg.interval}&range=${cfg.range}&includePrePost=true`;
    const r = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" }, cache: "no-store", signal: AbortSignal.timeout(5000) });
    if (r.ok) {
      const j = await r.json();
      const res = j?.chart?.result?.[0];
      const ts = res?.timestamp;
      const closes = res?.indicators?.quote?.[0]?.close;
      if (Array.isArray(ts) && Array.isArray(closes)) {
        // Classify each bar by exchange-local time-of-day (robust across multiple days,
        // unlike meta.tradingPeriods which Yahoo only returns for the current day).
        // Regular US equity session = 09:30–16:00 exchange-local; everything else = extended.
        const gmt = Number(res.meta?.gmtoffset) || 0; // seconds to add to UTC for exchange-local
        const REG_START = 9.5 * 3600, REG_END = 16 * 3600;
        const inReg = (t) => {
          const sod = (((t + gmt) % 86400) + 86400) % 86400;
          return sod >= REG_START && sod < REG_END;
        };
        for (let i = 0; i < ts.length; i++) {
          const c = closes[i];
          if (c == null) continue;
          candles.push({ t: ts[i], c: +Number(c).toFixed(2), ext: !inReg(ts[i]) });
        }
      }
    }
  } catch (_e) {
    /* fall through to empty list */
  }

  return Response.json(
    { symbol, range: rk, candles, asOf: Date.now() },
    { headers: { "Cache-Control": "s-maxage=60, stale-while-revalidate=120" } }
  );
}
