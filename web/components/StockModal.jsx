"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { money, pct, cls } from "../lib/format";
import { named } from "../lib/names";

// Intraday ranges hit Yahoo (5-min bars incl. pre/after-hours); daily ranges use the
// committed snapshot. "trades" frames the chart around the symbol's first paper trade.
const INTRA_RANGES = [
  { k: "1d", label: "1D" },
  { k: "5d", label: "5D" },
];
const DAILY_RANGES = [
  { k: "trades", label: "Trades" },
  { k: "1w", label: "1W", sessions: 5 },
  { k: "1m", label: "1M", sessions: 22 },
  { k: "3m", label: "3M", sessions: 64 },
  { k: "6m", label: "6M", sessions: 128 },
  { k: "all", label: "All" },
];
const isIntra = (k) => k === "1d" || k === "5d";

function extSpans(flags) {
  const out = [];
  let s = null;
  for (let i = 0; i < flags.length; i++) {
    if (flags[i] && s === null) s = i;
    else if (!flags[i] && s !== null) { out.push([s, i - 1]); s = null; }
  }
  if (s !== null) out.push([s, flags.length - 1]);
  return out;
}

// Drill-down for one ticker: price chart (daily snapshot or Yahoo intraday w/ extended
// hours) with each method's buy/sell markers, a live quote header, and recent headlines.
export default function StockModal({ symbol, data, history }) {
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
  const firstTradeDate = trades.length ? trades[0].date : null;

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

  const [range, setRange] = useState(trades.length ? "trades" : "3m");

  // Intraday candles (only when an intraday range is selected). null = loading.
  const [intra, setIntra] = useState(null);
  useEffect(() => {
    if (!isIntra(range)) { setIntra(null); return; }
    let alive = true;
    setIntra(null);
    fetch(`/api/intraday?symbol=${symbol}&range=${range}`)
      .then((r) => r.json())
      .then((j) => { if (alive) setIntra(j.candles || []); })
      .catch(() => { if (alive) setIntra([]); });
    return () => { alive = false; };
  }, [symbol, range]);

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  // Full daily series + a live "now" point so the daily line reaches the present.
  const fullSeries = useMemo(() => {
    const b = (history && history[symbol]) || [];
    if (quote && quote.price > 0 && b.length && today > b[b.length - 1][0]) {
      return [...b, [today, +Number(quote.price).toFixed(2)]];
    }
    return b;
  }, [history, symbol, quote, today]);

  const view = useMemo(() => {
    const fs = fullSeries;
    if (!fs.length) return fs;
    if (range === "trades" && firstTradeDate) {
      let idx = fs.findIndex((p) => p[0] >= firstTradeDate);
      if (idx === -1) idx = 0;
      return fs.slice(Math.max(0, idx - 2));
    }
    const r = DAILY_RANGES.find((x) => x.k === range);
    if (r && r.sessions) return fs.slice(-r.sessions);
    return fs;
  }, [fullSeries, range, firstTradeDate]);

  // Choose the chart's data: intraday [t,close] + ext flags, or daily [date,close].
  const intraday = isIntra(range);
  let pts, extFlags = null, loadingIntra = false, emptyIntra = false;
  if (intraday) {
    if (intra === null) { loadingIntra = true; pts = []; }
    else { pts = intra.map((c) => [c.t, c.c]); extFlags = intra.map((c) => c.ext); emptyIntra = pts.length < 2; }
  } else {
    pts = view;
  }
  const n = pts.length;
  const closes = pts.map((p) => p[1]);
  const fmtX = (v) =>
    intraday ? new Date(v * 1000).toLocaleString(undefined, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : v;

  const dateIdx = useMemo(() => new Map(view.map((p, i) => [p[0], i])), [view]);
  const markers = intraday ? [] : trades.map((t) => ({ ...t, i: dateIdx.get(t.date) })).filter((m) => m.i != null);

  const W = 720, H = 280, L = 48, R = 14, T = 16, B = 26;
  let chart;
  if (intraday && loadingIntra) {
    chart = <p className="pmute">Loading intraday…</p>;
  } else if (intraday && emptyIntra) {
    chart = <p className="pmute">Intraday unavailable for {symbol} right now (Yahoo feed).</p>;
  } else if (n >= 2) {
    let lo = Math.min(...closes, ...markers.map((m) => m.price));
    let hi = Math.max(...closes, ...markers.map((m) => m.price));
    const padR = (hi - lo) * 0.08 || 1;
    lo -= padR; hi += padR;
    const x = (i) => L + (i / (n - 1)) * (W - L - R);
    const y = (v) => T + (1 - (v - lo) / ((hi - lo) || 1)) * (H - T - B);
    const line = pts.map((p, i) => x(i).toFixed(1) + "," + y(p[1]).toFixed(1)).join(" ");
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
          {extFlags && extSpans(extFlags).map((sp, k) => {
            const x0 = x(Math.max(0, sp[0] - 0.5));
            return <rect key={k} x={x0} y={T} width={x(Math.min(n - 1, sp[1] + 0.5)) - x0} height={H - T - B} fill="var(--ink)" opacity="0.05" />;
          })}
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
          <text x={L} y={H - 9} fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">{fmtX(pts[0][0])}</text>
          <text x={W - R} y={H - 9} textAnchor="end" fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">{fmtX(pts[n - 1][0])}</text>
          {hover != null && (
            <>
              <line x1={x(hover)} y1={T} x2={x(hover)} y2={H - B} stroke="var(--ink)" strokeOpacity="0.28" />
              <circle cx={x(hover)} cy={y(closes[hover])} r="3.5" fill="var(--signal)" />
            </>
          )}
        </svg>
        {hover != null && (
          <div className="rtt" style={{ opacity: 1, left: `${Math.min(82, (hover / (n - 1)) * 100)}%`, top: "10px" }}>
            <div className="rt-d">{fmtX(pts[hover][0])}{!intraday && pts[hover][0] === today ? " · now" : ""}{intraday && extFlags[hover] ? " · ext" : ""}</div>
            <div className="rt-r"><span>{intraday ? "price" : "close"}</span><span>{money(closes[hover])}</span></div>
          </div>
        )}
      </div>
    );
  } else {
    chart = <p className="pmute">Not enough data for {symbol} in this range.</p>;
  }

  const rangeBtn = (r) => (
    <button key={r.k} className={"rbtn" + (range === r.k ? " on" : "")} onClick={() => { setRange(r.k); setHover(null); }}>{r.label}</button>
  );

  return (
    <>
      <div className="modal-eyebrow">Stock · {intraday ? (range === "1d" ? "intraday" : "5-day intraday") : (view.length ? `${view[0][0]} → ${view[view.length - 1][0]}` : "snapshot")}</div>
      <div className="stockhd">
        <h3>{named(symbol)}</h3>
        {quote ? (
          <div className="stockpx">
            <span className="mono px">{money(quote.price)}</span>
            <span className={"mono " + cls(quote.pct)}>{pct((quote.pct || 0) / 100)} ({quote.change >= 0 ? "+" : ""}{(quote.change || 0).toFixed(2)})</span>
          </div>
        ) : <span className="pmute" style={{ fontSize: ".8rem" }}>live quote…</span>}
      </div>
      {heldBy.length > 0 && <p className="note" style={{ marginTop: 0 }}>Currently held by <b>{heldBy.join(", ")}</b>.</p>}

      <div className="rangebar">
        {INTRA_RANGES.map(rangeBtn)}
        <span className="rdiv" />
        {DAILY_RANGES.filter((r) => r.k !== "trades" || trades.length).map(rangeBtn)}
      </div>

      {chart}
      {intraday ? (
        <div className="mklegend">
          <span><i className="extsw" />pre / after-hours</span>
          <span className="pmute">5-min bars from Yahoo · shaded = extended hours · hover for price</span>
        </div>
      ) : (
        <div className="mklegend">
          <span><i className="mk buy" />buy</span>
          <span><i className="mk sell" />sell</span>
          <span className="pmute">markers = where each method traded {symbol} · hover for the close</span>
        </div>
      )}

      {trades.length > 0 && (
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
      <p className="note">
        {intraday
          ? "Intraday = Yahoo 5-min bars incl. pre/after-hours (unofficial feed). News & the daily quote via Finnhub."
          : "Daily closes from the bots' data snapshot; the rightmost point is today's live Finnhub quote. Markers are the forward paper trades."}
      </p>
    </>
  );
}
