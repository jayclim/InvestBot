"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { money, pct, cls } from "../lib/format";

// Drill-down for one ticker: daily close chart from the bots' snapshot, with every
// competitor's buy/sell markers overlaid, a live quote header, and recent headlines.
export default function StockModal({ symbol, data, history }) {
  const series = (history && history[symbol]) || [];
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);

  const trades = useMemo(() => {
    const out = [];
    (data.competitors || []).forEach((c) =>
      (c.trade_log || []).forEach((t) => {
        if (t.symbol === symbol) out.push({ ...t, who: c.name });
      })
    );
    return out.sort((a, b) => (a.date < b.date ? -1 : 1));
  }, [data, symbol]);

  const heldBy = (data.competitors || [])
    .filter((c) => (c.holdings || []).some((h) => h.symbol === symbol))
    .map((c) => c.name.split("_")[0]);

  const [quote, setQuote] = useState(null);
  const [news, setNews] = useState(null); // null = loading, [] = none
  useEffect(() => {
    let alive = true;
    fetch("/api/quotes?symbols=" + symbol, { cache: "no-store" })
      .then((r) => r.json())
      .then((j) => { if (alive) setQuote((j.quotes || {})[symbol] || null); })
      .catch(() => {});
    fetch("/api/news?symbol=" + symbol)
      .then((r) => r.json())
      .then((j) => { if (alive) setNews(j.news || []); })
      .catch(() => { if (alive) setNews([]); });
    return () => { alive = false; };
  }, [symbol]);

  const W = 720, H = 280, L = 48, R = 14, T = 16, B = 26;
  const n = series.length;
  const closes = series.map((p) => p[1]);
  const dateIdx = useMemo(() => new Map(series.map((p, i) => [p[0], i])), [series]);
  const markers = trades.map((t) => ({ ...t, i: dateIdx.get(t.date) })).filter((m) => m.i != null);

  let chart = null;
  if (n >= 2) {
    let lo = Math.min(...closes, ...markers.map((m) => m.price));
    let hi = Math.max(...closes, ...markers.map((m) => m.price));
    const padR = (hi - lo) * 0.08 || 1;
    lo -= padR; hi += padR;
    const x = (i) => L + (i / (n - 1)) * (W - L - R);
    const y = (v) => T + (1 - (v - lo) / ((hi - lo) || 1)) * (H - T - B);
    const line = series.map((p, i) => x(i).toFixed(1) + "," + y(p[1]).toFixed(1)).join(" ");
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => lo + f * (hi - lo));
    const tri = (cx, cy, s, up) =>
      up ? `${cx},${cy - s} ${cx - s},${cy + s} ${cx + s},${cy + s}`
         : `${cx},${cy + s} ${cx - s},${cy - s} ${cx + s},${cy - s}`;

    function onMove(e) {
      const svg = svgRef.current;
      const pt = svg.createSVGPoint();
      const t = e.touches ? e.touches[0] : e;
      pt.x = t.clientX; pt.y = t.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      let idx = Math.round(((loc.x - L) / (W - L - R)) * (n - 1));
      idx = Math.max(0, Math.min(n - 1, idx));
      setHover(idx);
    }

    chart = (
      <div className="chartwrap">
        <svg
          ref={svgRef}
          className="chart stockchart"
          viewBox={`0 0 ${W} ${H}`}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          onTouchMove={onMove}
          onTouchEnd={() => setHover(null)}
        >
          {ticks.map((v, i) => (
            <g key={i}>
              <line x1={L} y1={y(v)} x2={W - R} y2={y(v)} stroke="var(--line-2)" />
              <text x={L - 7} y={y(v) + 3.5} textAnchor="end" fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">
                {v.toFixed(v < 10 ? 2 : 0)}
              </text>
            </g>
          ))}
          <polyline points={line} fill="none" stroke="var(--signal)" strokeWidth="1.8" strokeLinejoin="round" />
          {markers.map((m, k) => (
            <polygon
              key={k}
              points={tri(x(m.i), y(m.price), 5, m.side === "buy")}
              fill={m.side === "buy" ? "var(--up)" : "var(--down)"}
              stroke="var(--surface)"
              strokeWidth="1"
            >
              <title>{`${m.who} · ${m.side} ${symbol} @ ${money(m.price)} · ${m.date}${m.reason ? " · " + m.reason : ""}`}</title>
            </polygon>
          ))}
          <text x={L} y={H - 9} fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">{series[0][0]}</text>
          <text x={W - R} y={H - 9} textAnchor="end" fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">{series[n - 1][0]}</text>
          {hover != null && (
            <>
              <line x1={x(hover)} y1={T} x2={x(hover)} y2={H - B} stroke="var(--ink)" strokeOpacity="0.28" />
              <circle cx={x(hover)} cy={y(closes[hover])} r="3.5" fill="var(--signal)" />
            </>
          )}
        </svg>
        {hover != null && (
          <div className="rtt" style={{ opacity: 1, left: `${Math.min(82, (hover / (n - 1)) * 100)}%`, top: "10px" }}>
            <div className="rt-d">{series[hover][0]}</div>
            <div className="rt-r"><span>close</span><span>{money(closes[hover])}</span></div>
          </div>
        )}
      </div>
    );
  } else {
    chart = <p className="pmute">No price history for {symbol} in the snapshot.</p>;
  }

  const up = (quote?.pct || 0) >= 0;
  return (
    <>
      <div className="modal-eyebrow">Stock · {series.length ? `${series[0][0]} → ${series[n - 1][0]}` : "snapshot"}</div>
      <div className="stockhd">
        <h3>{symbol}</h3>
        {quote ? (
          <div className="stockpx">
            <span className="mono px">{money(quote.price)}</span>
            <span className={"mono " + cls(quote.pct)}>{pct((quote.pct || 0) / 100)} ({quote.change >= 0 ? "+" : ""}{(quote.change || 0).toFixed(2)})</span>
          </div>
        ) : <span className="pmute" style={{ fontSize: ".8rem" }}>live quote…</span>}
      </div>
      {heldBy.length > 0 && <p className="note" style={{ marginTop: 0 }}>Currently held by <b>{heldBy.join(", ")}</b>.</p>}

      {chart}
      <div className="mklegend">
        <span><i className="mk buy" />buy</span>
        <span><i className="mk sell" />sell</span>
        <span className="pmute">markers = where each method traded {symbol} · hover for the close</span>
      </div>

      {markers.length > 0 && (
        <table className="tl">
          <thead><tr><th>date</th><th>method</th><th>side</th><th>price</th><th>P&amp;L</th></tr></thead>
          <tbody>
            {trades.slice().reverse().map((t, i) => (
              <tr key={i}>
                <td>{t.date}</td>
                <td>{t.who.split("_")[0]}</td>
                <td className="mono" style={{ color: t.side === "buy" ? "var(--up)" : "var(--down)" }}>{t.side}</td>
                <td className="mono">{money(t.price)}</td>
                <td className={"mono " + (t.pnl ? cls(t.pnl) : "")}>{t.pnl ? (t.pnl >= 0 ? "+" : "") + t.pnl.toFixed(2) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="newshd">Recent news</div>
      {news === null && <p className="pmute">Loading headlines…</p>}
      {news !== null && news.length === 0 && <p className="pmute">No recent headlines (or the news feed is unavailable).</p>}
      {news && news.length > 0 && (
        <ul className="news">
          {news.map((a, i) => (
            <li key={i} className="newsitem">
              <a href={a.url} target="_blank" rel="noreferrer">{a.headline}</a>
              <div className="meta mono">{a.source}{a.datetime ? " · " + new Date(a.datetime * 1000).toLocaleDateString() : ""}</div>
            </li>
          ))}
        </ul>
      )}
      <p className="note">Chart = daily closes from the bots&apos; data snapshot (as of the last refresh); markers are the forward paper trades. Live quote &amp; news via Finnhub.</p>
    </>
  );
}
