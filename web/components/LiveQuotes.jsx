"use client";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

// One shared live-quote feed for the whole page. Standings, equity curves, and the
// live-prices grid all read from here so we poll Finnhub (/api/quotes) once, not 3×.
const Ctx = createContext({ quotes: {}, asOf: "", live: false });

// Everything the bots hold or are voting on — bounded to the route's fan-out cap (30).
export function feedSymbols(data) {
  const s = new Set();
  if (data.benchmark?.symbol) s.add(data.benchmark.symbol); // S&P proxy — live-marks the benchmark line
  (data.competitors || []).forEach((c) => (c.holdings || []).forEach((h) => s.add(h.symbol)));
  if (data.analyst?.targets) Object.keys(data.analyst.targets).forEach((x) => s.add(x));
  if (data.swarm?.ballots) data.swarm.ballots.slice(0, 6).forEach(([sym]) => { if (sym !== "CASH") s.add(sym); });
  return [...s].slice(0, 30);
}

export function LiveQuotesProvider({ data, children }) {
  const symbols = useMemo(() => feedSymbols(data), [data]);
  const [quotes, setQuotes] = useState({});
  const [asOf, setAsOf] = useState("connecting…");

  useEffect(() => {
    if (!symbols.length) { setAsOf(""); return; }
    let alive = true;
    async function poll() {
      try {
        const r = await fetch("/api/quotes?symbols=" + symbols.join(","), { cache: "no-store" });
        const j = await r.json();
        if (!alive) return;
        const fresh = j.quotes || {};
        // Merge over last-known: a symbol Finnhub drops this cycle keeps its prior price instead
        // of blanking to "…". That intermittent partial response is what made tiles flicker.
        setQuotes((prev) => ({ ...prev, ...fresh }));
        const n = Object.keys(fresh).length;
        setAsOf(n ? `${n} symbols · updated ${new Date(j.asOf).toLocaleTimeString()}` : "no quotes (check FINNHUB_API_KEY)");
      } catch (_e) {
        if (alive) setAsOf("live feed unavailable — run `next dev` or deploy to Vercel");
      }
    }
    poll();
    const id = setInterval(poll, 15000);
    return () => { alive = false; clearInterval(id); };
  }, [symbols]);

  const value = useMemo(
    () => ({ quotes, asOf, live: Object.keys(quotes).length > 0 }),
    [quotes, asOf]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useLiveQuotes = () => useContext(Ctx);

// Re-mark a competitor's book to live prices: equity = cash + Σ qty·price, where price is
// the live quote when available else the stored per-tick mark (`last`, the latest snapshot
// close). With markets closed / no feed this reproduces the published `final` exactly.
export function liveMark(c, quotes, startingCash) {
  let held = 0, priced = false;
  (c.holdings || []).forEach((h) => {
    const q = quotes[h.symbol];
    const live = q && q.price > 0;
    if (live) priced = true;
    held += h.qty * (live ? q.price : (h.last != null ? h.last : h.avg_price));
  });
  const equity = c.cash + held;
  return { equity, ret: equity / startingCash - 1, priced };
}
