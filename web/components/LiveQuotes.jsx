"use client";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

// One shared live-quote feed for the whole page. Standings, equity curves, and the
// live-prices grid all read from here so we poll Finnhub (/api/quotes) once, not 3×.
const Ctx = createContext({ quotes: {}, asOf: "", live: false });

// Everything the bots hold or are voting on — bounded to the route's fan-out cap (30).
export function feedSymbols(data) {
  const s = new Set();
  if (data.benchmark?.symbol) s.add(data.benchmark.symbol); // S&P proxy — live-marks the benchmark line
  (data.competitors || []).forEach((c) => {
    (c.holdings || []).forEach((h) => s.add(h.symbol));
    (c.open_orders || []).forEach((o) => s.add(o.symbol)); // queued names need quotes to simulate fills
  });
  if (data.analyst?.targets) Object.keys(data.analyst.targets).forEach((x) => s.add(x));
  if (data.swarm?.ballots) data.swarm.ballots.slice(0, 6).forEach(([sym]) => { if (sym !== "CASH") s.add(sym); });
  return [...s].slice(0, 30);
}

// Prior-close seed so tiles paint a (greyed) price immediately instead of "…" while the first
// Finnhub poll is in flight. `last` is the unscaled per-tick mark already in state.json.
function seedFromMarks(data) {
  const m = {};
  (data.competitors || []).forEach((c) =>
    (c.holdings || []).forEach((h) => {
      if (h.last != null && m[h.symbol] == null) m[h.symbol] = { price: h.last, stale: true };
    })
  );
  return m;
}

export function LiveQuotesProvider({ data, children }) {
  const symbols = useMemo(() => feedSymbols(data), [data]);
  const [quotes, setQuotes] = useState(() => seedFromMarks(data));
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
    // 30s keeps us under Finnhub free's 60 calls/min (one call per symbol × ~22 symbols);
    // 15s overran it, so each cycle only a rotating subset survived and tiles showed "…".
    const id = setInterval(poll, 30000);
    return () => { alive = false; clearInterval(id); };
  }, [symbols]);

  const value = useMemo(
    () => ({ quotes, asOf, live: Object.keys(quotes).length > 0 }),
    [quotes, asOf]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useLiveQuotes = () => useContext(Ctx);

// ET wall-clock date + minutes-since-midnight of a unix-seconds timestamp.
function etParts(unixSec) {
  const p = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", hour12: false,
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).formatToParts(new Date(unixSec * 1000)).reduce((a, x) => ((a[x.type] = x.value), a), {});
  return { date: `${p.year}-${p.month}-${p.day}`, mins: +p.hour * 60 + +p.minute };
}

// The price a queued order "should have filled" at, or null if it hasn't. A queued order fills
// at the first session AFTER placed_session; the quote's open/high/low describe the session of
// its last trade (t), so if that session is later than placed_session and past 9:30 ET we apply
// the same rule the tick does (paper._fill_price): MOO at the open, a limit only if the day
// traded through it. Display-only approximation — no slippage, and an order more than one
// session old fills at the LATEST session's open; the next run_agents tick settles it for real.
export function simFillPrice(o, q) {
  if (!(q && q.price > 0 && q.open > 0 && q.t && o.placed_session)) return null;
  const et = etParts(q.t);
  if (et.date <= o.placed_session || et.mins < 9 * 60 + 30) return null;
  if (o.kind !== "limit" || o.limit == null) return q.open;
  if (o.side === "buy") return q.low <= o.limit ? Math.min(q.open, o.limit) : null;
  return q.high >= o.limit ? Math.max(q.open, o.limit) : null;
}

// Re-mark a competitor's book to live prices: equity = cash + Σ qty·price, where price is
// the live quote when available else the stored per-tick mark (`last`, the latest snapshot
// close). Queued orders whose session has since opened are simulated as filled first (in plan
// order: sells free cash before buys spend it), so the live board already reflects them.
// `fills` = indices into c.open_orders treated as filled. With markets closed / no feed this
// reproduces the published `final` exactly (no quote → no simulated fill).
export function liveMark(c, quotes, startingCash) {
  let cash = c.cash, held = 0, priced = false;
  const pos = {};
  (c.holdings || []).forEach((h) => { pos[h.symbol] = { ...h }; });
  const fills = new Set();
  (c.open_orders || []).forEach((o, i) => {
    const q = quotes[o.symbol];
    const px = simFillPrice(o, q);
    if (px == null) return;
    if (o.side === "buy") {
      const spend = Math.min(o.dollars || 0, cash);
      if (spend <= 0) return;
      cash -= spend;
      const p = pos[o.symbol] || (pos[o.symbol] = { symbol: o.symbol, qty: 0, avg_price: px, last: px });
      p.qty += spend / px;
    } else {
      const p = pos[o.symbol];
      const qty = Math.min(o.qty != null ? o.qty : (p ? p.qty : 0), p ? p.qty : 0);
      if (!p || qty <= 0) return;
      cash += qty * px;
      p.qty -= qty;
    }
    fills.add(i);
  });
  Object.values(pos).forEach((h) => {
    const q = quotes[h.symbol];
    const live = q && q.price > 0;
    if (live) priced = true;
    held += h.qty * (live ? q.price : (h.last != null ? h.last : h.avg_price));
  });
  const equity = cash + held;
  return { equity, ret: equity / startingCash - 1, priced, fills };
}
