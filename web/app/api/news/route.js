// Serverless route: recent company news from Finnhub.
// GET /api/news?symbol=NVDA  ->  { news: [{ headline, source, url, datetime, summary }], asOf }
// FINNHUB_API_KEY is a Vercel env var, never sent to the client. CDN-cached 10 min.
// Degrades gracefully: missing key or upstream error -> empty list (the modal still renders).

export const dynamic = "force-dynamic";

const ymd = (d) => d.toISOString().slice(0, 10);

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const symbol = String(searchParams.get("symbol") || "").trim().toUpperCase();
  if (!symbol) return Response.json({ news: [], asOf: Date.now() });

  const key = process.env.FINNHUB_API_KEY;
  if (!key) return Response.json({ news: [], asOf: Date.now(), error: "FINNHUB_API_KEY not set" });

  const to = new Date();
  const from = new Date(to.getTime() - 30 * 24 * 60 * 60 * 1000);

  let news = [];
  try {
    const r = await fetch(
      `https://finnhub.io/api/v1/company-news?symbol=${encodeURIComponent(symbol)}&from=${ymd(from)}&to=${ymd(to)}&token=${key}`,
      { cache: "no-store" }
    );
    if (r.ok) {
      const j = await r.json();
      if (Array.isArray(j)) {
        news = j
          .filter((n) => n && n.headline)
          .slice(0, 8)
          .map((n) => ({
            headline: n.headline,
            source: n.source || "",
            url: n.url || "",
            datetime: n.datetime || 0,
            summary: (n.summary || "").slice(0, 280),
          }));
      }
    }
  } catch (_e) {
    /* fall through to empty list */
  }

  return Response.json(
    { news, asOf: Date.now() },
    { headers: { "Cache-Control": "s-maxage=600, stale-while-revalidate=1200" } }
  );
}
