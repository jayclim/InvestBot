"use client";
import { useRef, useState } from "react";
import { money, pct, cls, methodColor, BENCH_COLOR, BENCH_INK } from "../lib/format";
import { InfoButton } from "./ModalContext";
import { useLiveQuotes, liveMark } from "./LiveQuotes";

export default function EquityCurves({ data }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const { quotes, live } = useLiveQuotes();
  const W = 960, H = 400, L = 58, R = 18, T = 18, B = 34;
  const start = data.starting_cash;
  // Append a live-marked point to each curve so the lines extend to the current value.
  // All curves share one axis, so appending one point to every series keeps them aligned.
  const series = data.competitors
    .filter((c) => c.equity_curve && c.equity_curve.length >= 2)
    .map((c) => {
      const mk = liveMark(c, quotes, start);
      const curve = live ? [...c.equity_curve, ["live", Math.round(mk.equity * 100) / 100]] : c.equity_curve;
      return { ...c, equity_curve: curve, _ret: live ? mk.ret : c.return };
    });

  // S&P 500 benchmark — a separate dashed line (not a competitor) so it overlays the field.
  let bench = null;
  const bd = data.benchmark;
  if (bd && bd.equity_curve && bd.equity_curve.length >= 2) {
    const q = quotes[bd.symbol];
    const lastClose = bd.equity_curve[bd.equity_curve.length - 1][1];
    const liveVal = live ? (q && q.price > 0 ? Math.round((start * q.price / bd.base) * 100) / 100 : lastClose) : null;
    const curve = live ? [...bd.equity_curve, ["live", liveVal]] : bd.equity_curve;
    bench = { ...bd, equity_curve: curve, _ret: curve[curve.length - 1][1] / start - 1 };
  }

  let body;
  if (!series.length) {
    body = (
      <div className="card pad chartwrap">
        <svg className="chart" viewBox={`0 0 ${W} ${H}`}>
          <text x="20" y="40" fontFamily="JetBrains Mono" fontSize="12" fill="var(--muted)">
            Curves appear after the first tick.
          </text>
        </svg>
      </div>
    );
  } else {
    let maxN = 0, minR = 0, maxR = 0;
    const scan = bench ? [...series, bench] : series;
    scan.forEach((c) => {
      maxN = Math.max(maxN, c.equity_curve.length);
      c.equity_curve.forEach((p) => { const r = p[1] / start - 1; minR = Math.min(minR, r); maxR = Math.max(maxR, r); });
    });
    minR = Math.min(minR, -0.05); maxR = Math.max(maxR, 0.05);
    const x = (i) => L + (i / (maxN - 1)) * (W - L - R);
    const y = (r) => T + (1 - (r - minR) / ((maxR - minR) || 1)) * (H - T - B);
    const dts = series[0].equity_curve;

    function onMove(e) {
      const svg = svgRef.current;
      const pt = svg.createSVGPoint();
      const t = e.touches ? e.touches[0] : e;
      pt.x = t.clientX; pt.y = t.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      let idx = Math.round(((loc.x - L) / (W - L - R)) * (maxN - 1));
      idx = Math.max(0, Math.min(maxN - 1, idx));
      const card = svg.closest(".chartwrap").getBoundingClientRect();
      setHover({ idx, cx: t.clientX - card.left, cw: card.width, cy: t.clientY - card.top });
    }

    const ticks = [];
    for (let k = 0; k <= 4; k++) { const r = minR + (k / 4) * (maxR - minR); ticks.push(r); }

    body = (
      <div className="card pad chartwrap">
        <svg
          ref={svgRef}
          className="chart"
          viewBox={`0 0 ${W} ${H}`}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          onTouchMove={onMove}
          onTouchEnd={() => setHover(null)}
        >
          {ticks.map((r, i) => (
            <g key={i}>
              <line x1={L} y1={y(r)} x2={W - R} y2={y(r)} stroke="var(--line-2)" />
              <text x={L - 8} y={y(r) + 3.5} textAnchor="end" fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">
                {(r * 100 >= 0 ? "+" : "") + (r * 100).toFixed(0)}%
              </text>
            </g>
          ))}
          <line x1={L} y1={y(0)} x2={W - R} y2={y(0)} stroke="var(--ink)" strokeDasharray="2 3" />
          <text x={L} y={H - 12} fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">{dts[0][0]}</text>
          <text x={W - R} y={H - 12} textAnchor="end" fontFamily="JetBrains Mono" fontSize="10" fill="var(--muted)">{dts[dts.length - 1][0]}</text>
          {series.map((c, i) => {
            const pts = c.equity_curve.map((p, j) => x(j).toFixed(1) + "," + y(p[1] / start - 1).toFixed(1)).join(" ");
            const idx = c.name === "S&P 500";  // market baseline — dashed, like the old benchmark line
            return <polyline key={i} points={pts} fill="none" stroke={methodColor(c.name, data.competitors)} strokeWidth={idx ? 2.25 : 2} strokeDasharray={idx ? "7 4" : undefined} strokeLinejoin="round" />;
          })}
          {bench && (
            <polyline
              points={bench.equity_curve.map((p, j) => x(j).toFixed(1) + "," + y(p[1] / start - 1).toFixed(1)).join(" ")}
              fill="none" stroke={BENCH_COLOR} strokeWidth="2.25" strokeDasharray="7 4" strokeLinejoin="round"
            />
          )}
          {hover && (
            <>
              <line x1={x(hover.idx)} y1={T} x2={x(hover.idx)} y2={H - B} stroke="var(--ink)" strokeOpacity="0.3" />
              {series.map((c, i) => {
                const p = c.equity_curve[Math.min(hover.idx, c.equity_curve.length - 1)];
                return <circle key={i} cx={x(hover.idx)} cy={y(p[1] / start - 1)} r="3.5" fill={methodColor(c.name, data.competitors)} />;
              })}
              {bench && (() => {
                const p = bench.equity_curve[Math.min(hover.idx, bench.equity_curve.length - 1)];
                return <circle cx={x(hover.idx)} cy={y(p[1] / start - 1)} r="3.5" fill={BENCH_COLOR} />;
              })()}
            </>
          )}
        </svg>
        {hover && (
          <div
            className="rtt"
            style={{
              opacity: 1,
              // flip to the cursor's left when the tooltip (≈220px, see .rtt width) would
              // overflow the chart's right edge; clamp so it never leaves the container.
              left: (hover.cx + 16 + 220 > hover.cw ? Math.max(4, hover.cx - 16 - 220) : hover.cx + 16) + "px",
              top: hover.cy + 10 + "px",
            }}
          >
            <div className="rt-d">{(series[0].equity_curve[Math.min(hover.idx, series[0].equity_curve.length - 1)] || ["", 0])[0]}</div>
            {series.map((c, i) => {
              const p = c.equity_curve[Math.min(hover.idx, c.equity_curve.length - 1)];
              const r = p[1] / start - 1;
              return (
                <div className="rt-r" key={i}>
                  <span style={{ color: methodColor(c.name, data.competitors) }}>{c.name.split("_")[0]}</span>
                  <span>{money(p[1])} {pct(r)}</span>
                </div>
              );
            })}
            {bench && (() => {
              const p = bench.equity_curve[Math.min(hover.idx, bench.equity_curve.length - 1)];
              const r = p[1] / start - 1;
              return (
                <div className="rt-r">
                  <span style={{ color: BENCH_INK }}>S&amp;P 500</span>
                  <span>{money(p[1])} {pct(r)}</span>
                </div>
              );
            })()}
          </div>
        )}
        <div className="legend">
          {[...series].sort((a, b) => b._ret - a._ret).map((c, i) => (
            <span key={i}><i className="swatch" style={{ background: methodColor(c.name, data.competitors) }} />{c.name} <b className={"mono " + cls(c._ret)}>{pct(c._ret)}</b></span>
          ))}
          {bench && (
            <span>
              <i className="swatch" style={{ background: `repeating-linear-gradient(90deg, ${BENCH_COLOR} 0 5px, transparent 5px 9px)` }} />
              <b style={{ color: BENCH_COLOR }}>S&amp;P 500</b> <span className="note" style={{ margin: 0 }}>benchmark</span> <b className={"mono " + cls(bench._ret)}>{pct(bench._ret)}</b>
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <section>
      <div className="eyebrow">
        <span className="n">02</span>
        <h2>Equity curves</h2>
        <InfoButton title="Equity curves">
          Each line is a competitor&apos;s live forward account value, plotted as cumulative return. All five share one axis that starts from the common {"$" + start.toLocaleString()} origin, so they&apos;re directly comparable. The final point is re-marked to live quotes every 30s (labelled <span className="mono">live</span>); with the market closed it sits at the last tick&apos;s close. Hover to read every competitor&apos;s value on a session.
        </InfoButton>
        <span className="hint">{live ? "live tip" : "hover for values"} · {"$" + start.toLocaleString()} start</span>
      </div>
      {body}
    </section>
  );
}
