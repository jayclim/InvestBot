"use client";
import { useEffect, useMemo, useState } from "react";
import { pct, cls } from "../lib/format";
import { InfoButton } from "./ModalContext";

function quoteSymbols(data) {
  const s = new Set();
  (data.competitors || []).forEach((c) => (c.holdings || []).forEach((h) => s.add(h.symbol)));
  if (data.analyst?.targets) Object.keys(data.analyst.targets).forEach((x) => s.add(x));
  if (data.swarm?.ballots) data.swarm.ballots.slice(0, 6).forEach(([sym]) => { if (sym !== "CASH") s.add(sym); });
  return [...s].slice(0, 28);
}
function heldBy(data, sym) {
  const who = (data.competitors || [])
    .filter((c) => (c.holdings || []).some((h) => h.symbol === sym))
    .map((c) => c.name.split("_")[0]);
  return [...new Set(who)].join(", ");
}

export default function LivePrices({ data }) {
  const symbols = useMemo(() => quoteSymbols(data), [data]);
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
        setQuotes(j.quotes || {});
        const n = Object.keys(j.quotes || {}).length;
        setAsOf(n ? `${n} symbols · updated ${new Date(j.asOf).toLocaleTimeString()}` : "no quotes (check FINNHUB_API_KEY)");
      } catch (_e) {
        if (alive) setAsOf("live feed unavailable — run `next dev` or deploy to Vercel");
      }
    }
    poll();
    const id = setInterval(poll, 15000);
    return () => { alive = false; clearInterval(id); };
  }, [symbols]);

  return (
    <section>
      <div className="eyebrow">
        <span className="n live-n">●</span>
        <h2>Live prices</h2>
        <InfoButton title="Live prices">
          Real-time-ish quotes from Finnhub via the <span className="mono">/api/quotes</span> serverless function, polled every 15 seconds. Shows everything the bots hold or are voting on. A public market feed — separate from your Robinhood account.
        </InfoButton>
        <span className="hint">{asOf}</span>
      </div>
      {symbols.length ? (
        <div className="pricegrid">
          {symbols.map((s) => {
            const q = quotes[s];
            const up = (q?.pct || 0) >= 0;
            return (
              <div key={s} className={"pcard " + (q ? (up ? "up" : "down") : "")}>
                <div className="sym">{s}<span className="by">{heldBy(data, s)}</span></div>
                <div className={"px" + (q ? "" : " pmute")}>{q ? "$" + q.price.toFixed(2) : "…"}</div>
                <div className={"chg " + (q ? cls(q.pct) : "")}>
                  {q ? `${pct((q.pct || 0) / 100)} (${q.change >= 0 ? "+" : ""}${(q.change || 0).toFixed(2)})` : ""}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="pmute">No holdings yet — run a tick.</p>
      )}
    </section>
  );
}
