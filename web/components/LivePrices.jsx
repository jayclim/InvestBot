"use client";
import { useMemo } from "react";
import { pct, cls } from "../lib/format";
import { InfoButton, useModal } from "./ModalContext";
import { useLiveQuotes, feedSymbols } from "./LiveQuotes";

function heldBy(data, sym) {
  const who = (data.competitors || [])
    .filter((c) => (c.holdings || []).some((h) => h.symbol === sym))
    .map((c) => c.name.split("_")[0]);
  return [...new Set(who)].join(", ");
}

export default function LivePrices({ data }) {
  const { openStock } = useModal();
  const { quotes, asOf } = useLiveQuotes();
  const symbols = useMemo(() => feedSymbols(data), [data]);

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
              <div
                key={s}
                className={"pcard clk " + (q ? (up ? "up" : "down") : "")}
                onClick={() => openStock(s)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openStock(s); } }}
              >
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
