"use client";
import { useRef, useState } from "react";
import { money, pct, cls, RCOL } from "../lib/format";
import { InfoButton } from "./ModalContext";

export default function EquityCurves({ data }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const W = 960, H = 400, L = 58, R = 18, T = 18, B = 34;
  const start = data.starting_cash;
  const series = data.competitors.filter((c) => c.equity_curve && c.equity_curve.length >= 2);

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
    series.forEach((c) => {
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
            return <polyline key={i} points={pts} fill="none" stroke={RCOL[i % RCOL.length]} strokeWidth="2" strokeLinejoin="round" />;
          })}
          {hover && (
            <>
              <line x1={x(hover.idx)} y1={T} x2={x(hover.idx)} y2={H - B} stroke="var(--ink)" strokeOpacity="0.3" />
              {series.map((c, i) => {
                const p = c.equity_curve[Math.min(hover.idx, c.equity_curve.length - 1)];
                return <circle key={i} cx={x(hover.idx)} cy={y(p[1] / start - 1)} r="3.5" fill={RCOL[i % RCOL.length]} />;
              })}
            </>
          )}
        </svg>
        {hover && (
          <div
            className="rtt"
            style={{
              opacity: 1,
              left: (hover.cx > hover.cw - 170 ? hover.cx - 166 : hover.cx + 14) + "px",
              top: hover.cy + 10 + "px",
            }}
          >
            <div className="rt-d">{(series[0].equity_curve[Math.min(hover.idx, series[0].equity_curve.length - 1)] || ["", 0])[0]}</div>
            {series.map((c, i) => {
              const p = c.equity_curve[Math.min(hover.idx, c.equity_curve.length - 1)];
              const r = p[1] / start - 1;
              return (
                <div className="rt-r" key={i}>
                  <span style={{ color: RCOL[i % RCOL.length] }}>{c.name.split("_")[0]}</span>
                  <span>{money(p[1])} {pct(r)}</span>
                </div>
              );
            })}
          </div>
        )}
        <div className="legend">
          {series.map((c, i) => (
            <span key={i}><i className="swatch" style={{ background: RCOL[i % RCOL.length] }} />{c.name} <b className={"mono " + cls(c.return)}>{pct(c.return)}</b></span>
          ))}
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
          Each line is a competitor&apos;s live forward account value, plotted as cumulative return. All five share one axis that starts from the common $100 origin, so they&apos;re directly comparable. Hover to read every competitor&apos;s value on a session.
        </InfoButton>
        <span className="hint">hover for values · $100 start</span>
      </div>
      {body}
    </section>
  );
}
