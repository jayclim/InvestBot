"use client";
import { useRef, useState } from "react";
import { money, pct, cls, methodColor, BENCH_COLOR, BENCH_INK } from "../lib/format";
import { InfoButton } from "./ModalContext";
import { useLiveQuotes, liveMark } from "./LiveQuotes";

// Short display names for the end-of-line labels.
const SHORT = {
  deep_research_analyst: "analyst",
  llm_voters: "voters",
  momentum_breakout: "momentum",
  mean_reversion: "mean-rev",
  blended_momo_rsi: "blended",
  mirofish_real: "mirofish",
  congress_mirror: "congress",
};
const short = (n) => SHORT[n] || n;

export default function EquityCurves({ data }) {
  const svgRef = useRef(null);
  const [hover, setHover] = useState(null);
  const [mode, setMode] = useState("$"); // "$" (absolute) | "spy" (each book divided by the benchmark)
  const { quotes, live } = useLiveQuotes();
  const W = 960, H = 400, L = 58, R = 128, T = 18, B = 34;
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

  // vs-SPY reference — today the S&P 500 line lives inside `series` (data.benchmark is null),
  // but fall back to the standalone `bench` line for older state.json shapes.
  const spyBase = series.find((c) => c.name === "S&P 500") || bench;
  const hasSpy = !!(spyBase && spyBase.equity_curve && spyBase.equity_curve.length >= 2);
  const vsSpy = mode === "spy" && hasSpy;
  // value_i -> start * (v_i / spy_i) — the S&P 500's own line divides by itself and goes dead flat.
  const relToSpy = (curve) => curve.map((p, i) => {
    const spyVal = spyBase.equity_curve[Math.min(i, spyBase.equity_curve.length - 1)][1];
    return [p[0], spyVal ? start * (p[1] / spyVal) : p[1]];
  });
  const plotSeries = vsSpy
    ? series.map((c) => { const ec = relToSpy(c.equity_curve); return { ...c, equity_curve: ec, _ret: ec[ec.length - 1][1] / start - 1 }; })
    : series;
  const plotBench = vsSpy && bench
    ? (() => { const ec = relToSpy(bench.equity_curve); return { ...bench, equity_curve: ec, _ret: ec[ec.length - 1][1] / start - 1 }; })()
    : bench;

  // Luck band: 200 random 5-name buy-and-hold portfolios' p10/p50/p90, same transform in vs-SPY mode.
  const bandRaw = data.luck?.band || [];
  const band = bandRaw.map((row, i) => {
    if (!vsSpy) return row;
    const spyVal = spyBase.equity_curve[Math.min(i, spyBase.equity_curve.length - 1)][1];
    const f = spyVal ? start / spyVal : 1;
    return [row[0], row[1] * f, row[2] * f, row[3] * f];
  });

  let body;
  if (!series.length) {
    body = (
      <div className="card pad chartwrap">
        <svg className="chart" viewBox={`0 0 ${W} ${H}`}>
          <text x="20" y="40" fontFamily="IBM Plex Mono" fontSize="12" fill="var(--muted)">
            Curves appear after the first tick.
          </text>
        </svg>
      </div>
    );
  } else {
    let maxN = 0, minR = 0, maxR = 0;
    const scan = plotBench ? [...plotSeries, plotBench] : plotSeries;
    scan.forEach((c) => {
      maxN = Math.max(maxN, c.equity_curve.length);
      c.equity_curve.forEach((p) => { const r = p[1] / start - 1; minR = Math.min(minR, r); maxR = Math.max(maxR, r); });
    });
    // the luck band must never clip, even when it's wider than every competitor
    band.forEach((row) => {
      [row[1], row[3]].forEach((v) => { const r = v / start - 1; minR = Math.min(minR, r); maxR = Math.max(maxR, r); });
    });
    minR = Math.min(minR, -0.05); maxR = Math.max(maxR, 0.05);
    const x = (i) => L + (i / (maxN - 1)) * (W - L - R);
    const y = (r) => T + (1 - (r - minR) / ((maxR - minR) || 1)) * (H - T - B);
    const dts = plotSeries[0].equity_curve;

    // Direct end-labels (name + live return) at each line's right terminus, in the
    // line's own colour — the legend only survives on phones. A 1-D relaxation pass
    // spreads any labels that would collide.
    const GAP = 13;
    const labels = [
      ...plotSeries.map((c) => {
        const last = c.equity_curve[c.equity_curve.length - 1];
        return { name: short(c.name), color: methodColor(c.name, data.competitors), ret: c._ret, ly: y(last[1] / start - 1) };
      }),
      ...(plotBench ? [(() => {
        const last = plotBench.equity_curve[plotBench.equity_curve.length - 1];
        return { name: "S&P 500", color: BENCH_COLOR, ret: plotBench._ret, ly: y(last[1] / start - 1) };
      })()] : []),
    ].sort((a, b) => a.ly - b.ly);
    labels.forEach((l) => { l.ty = Math.max(T + 4, Math.min(H - B, l.ly)); });
    for (let i = 1; i < labels.length; i++) labels[i].ty = Math.max(labels[i].ty, labels[i - 1].ty + GAP);
    for (let i = labels.length - 1; i >= 0; i--) {
      labels[i].ty = Math.min(labels[i].ty, (i === labels.length - 1 ? H - B : labels[i + 1].ty - GAP));
    }

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

    // Drawdown strip — always from the ABSOLUTE curves (peak-to-trough), independent of the
    // $/vs-SPY toggle: it's a risk fingerprint, not a return view.
    const H2 = 110, T2 = 14, B2 = 20;
    const ddOf = (curve) => { let peak = -Infinity; return curve.map((p) => { peak = Math.max(peak, p[1]); return p[1] / peak - 1; }); };
    const ddSeries = series.map((c) => ({ name: c.name, dd: ddOf(c.equity_curve) }));
    const ddBenchLine = bench ? ddOf(bench.equity_curve) : null;
    let worstDd = 0;
    ddSeries.forEach((s) => s.dd.forEach((v) => { worstDd = Math.min(worstDd, v); }));
    if (ddBenchLine) ddBenchLine.forEach((v) => { worstDd = Math.min(worstDd, v); });
    const ddLo = Math.min(-0.10, worstDd);
    const y2 = (dd) => T2 + (1 - (dd - ddLo) / ((0 - ddLo) || 1)) * (H2 - T2 - B2);

    body = (
      <div className="card pad chartwrap">
        {hasSpy && (
          <div className="rangebar">
            <button className={"rbtn" + (mode === "$" ? " on" : "")} onClick={() => setMode("$")}>$</button>
            <button className={"rbtn" + (mode === "spy" ? " on" : "")} onClick={() => setMode("spy")}>vs SPY</button>
          </div>
        )}
        <svg
          ref={svgRef}
          className="chart"
          viewBox={`0 0 ${W} ${H}`}
          onMouseMove={onMove}
          onMouseLeave={() => setHover(null)}
          onTouchMove={onMove}
          onTouchEnd={() => setHover(null)}
        >
          {band.length > 1 && (() => {
            const top = band.map((row, i) => `${x(i).toFixed(1)},${y(row[3] / start - 1).toFixed(1)}`);
            const bot = band.map((row, i) => `${x(i).toFixed(1)},${y(row[1] / start - 1).toFixed(1)}`).reverse();
            const med = band.map((row, i) => `${x(i).toFixed(1)},${y(row[2] / start - 1).toFixed(1)}`).join(" ");
            return (
              <>
                <polygon points={[...top, ...bot].join(" ")} fill="var(--ink)" fillOpacity="0.055" stroke="none" />
                <polyline points={med} fill="none" stroke="var(--muted)" strokeWidth="1" strokeDasharray="1 2" opacity="0.6" />
              </>
            );
          })()}
          {ticks.map((r, i) => (
            <g key={i}>
              <line x1={L} y1={y(r)} x2={W - R} y2={y(r)} stroke="var(--line-2)" />
              <text x={L - 8} y={y(r) + 3.5} textAnchor="end" fontFamily="IBM Plex Mono" fontSize="10" fill="var(--muted)">
                {(r * 100 >= 0 ? "+" : "") + (r * 100).toFixed(0)}%
              </text>
            </g>
          ))}
          <line x1={L} y1={y(0)} x2={W - R} y2={y(0)} stroke="var(--ink)" strokeDasharray="2 3" />
          <text x={L} y={H - 12} fontFamily="IBM Plex Mono" fontSize="10" fill="var(--muted)">{dts[0][0]}</text>
          <text x={W - R} y={H - 12} textAnchor="end" fontFamily="IBM Plex Mono" fontSize="10" fill="var(--muted)">{dts[dts.length - 1][0]}</text>
          {plotSeries.map((c, i) => {
            const pts = c.equity_curve.map((p, j) => x(j).toFixed(1) + "," + y(p[1] / start - 1).toFixed(1)).join(" ");
            const idx = c.name === "S&P 500";  // market baseline — dashed, like the old benchmark line
            return (
              <polyline
                key={i}
                points={pts}
                fill="none"
                stroke={methodColor(c.name, data.competitors)}
                strokeWidth={idx ? 2.25 : 2}
                strokeDasharray={idx ? "7 4" : undefined}
                strokeLinejoin="round"
                pathLength={idx ? undefined : 1}
                className={idx ? undefined : "drawline"}
              />
            );
          })}
          {plotBench && (
            <polyline
              points={plotBench.equity_curve.map((p, j) => x(j).toFixed(1) + "," + y(p[1] / start - 1).toFixed(1)).join(" ")}
              fill="none" stroke={BENCH_COLOR} strokeWidth="2.25" strokeDasharray="7 4" strokeLinejoin="round"
            />
          )}
          {/* the shared $100 origin every line leaves from */}
          <circle cx={x(0)} cy={y(0)} r="3.5" fill="var(--paper)" stroke="var(--ink)" strokeWidth="1.2" />
          {labels.map((l, i) => (
            <g key={i} className="endlab">
              <line x1={W - R + 2} y1={l.ly} x2={W - R + 8} y2={l.ty} stroke={l.color} strokeWidth="1" opacity="0.55" />
              <text x={W - R + 11} y={l.ty + 3.5} fontFamily="IBM Plex Mono" fontSize="11" fill={l.color}>
                {l.name} <tspan fontWeight="600">{pct(l.ret)}</tspan>
              </text>
            </g>
          ))}
          {hover && (
            <>
              <line x1={x(hover.idx)} y1={T} x2={x(hover.idx)} y2={H - B} stroke="var(--ink)" strokeOpacity="0.3" />
              {plotSeries.map((c, i) => {
                const p = c.equity_curve[Math.min(hover.idx, c.equity_curve.length - 1)];
                return <circle key={i} cx={x(hover.idx)} cy={y(p[1] / start - 1)} r="3.5" fill={methodColor(c.name, data.competitors)} />;
              })}
              {plotBench && (() => {
                const p = plotBench.equity_curve[Math.min(hover.idx, plotBench.equity_curve.length - 1)];
                return <circle cx={x(hover.idx)} cy={y(p[1] / start - 1)} r="3.5" fill={BENCH_COLOR} />;
              })()}
            </>
          )}
        </svg>

        {/* drawdown strip — a slim second plate under the field, x-aligned, no interaction */}
        <svg className="chart" viewBox={`0 0 ${W} ${H2}`} style={{ marginTop: "4px" }} aria-label="Drawdown from peak">
          <text x={L} y="11" fontFamily="IBM Plex Mono" fontSize="10" fill="var(--muted)">drawdown from peak</text>
          <line x1={L} y1={y2(0)} x2={W - R} y2={y2(0)} stroke="var(--line-2)" />
          <text x={L - 8} y={y2(0) + 3.5} textAnchor="end" fontFamily="IBM Plex Mono" fontSize="10" fill="var(--muted)">0%</text>
          <text x={L - 8} y={y2(ddLo) + 3.5} textAnchor="end" fontFamily="IBM Plex Mono" fontSize="10" fill="var(--muted)">{(ddLo * 100).toFixed(0)}%</text>
          {ddSeries.map((s, i) => {
            const idx = s.name === "S&P 500";
            return (
              <polyline
                key={i}
                points={s.dd.map((v, j) => x(j).toFixed(1) + "," + y2(v).toFixed(1)).join(" ")}
                fill="none" stroke={methodColor(s.name, data.competitors)} strokeWidth="1.2"
                strokeDasharray={idx ? "6 3" : undefined} strokeLinejoin="round"
              />
            );
          })}
          {ddBenchLine && (
            <polyline
              points={ddBenchLine.map((v, j) => x(j).toFixed(1) + "," + y2(v).toFixed(1)).join(" ")}
              fill="none" stroke={BENCH_COLOR} strokeWidth="1.2" strokeDasharray="6 3" strokeLinejoin="round"
            />
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
            <div className="rt-d">{(plotSeries[0].equity_curve[Math.min(hover.idx, plotSeries[0].equity_curve.length - 1)] || ["", 0])[0]}</div>
            {[...plotSeries]
              .map((c) => ({ c, p: c.equity_curve[Math.min(hover.idx, c.equity_curve.length - 1)] }))
              .sort((a, b) => b.p[1] - a.p[1])  // rank by THIS day's value, not the current standings
              .map(({ c, p }) => {
                const r = p[1] / start - 1;
                return (
                  <div className="rt-r" key={c.name}>
                    <span style={{ color: methodColor(c.name, data.competitors) }}>{short(c.name)}</span>
                    <span>{vsSpy ? pct(r) : <>{money(p[1])} {pct(r)}</>}</span>
                  </div>
                );
              })}
            {plotBench && (() => {
              const p = plotBench.equity_curve[Math.min(hover.idx, plotBench.equity_curve.length - 1)];
              const r = p[1] / start - 1;
              return (
                <div className="rt-r">
                  <span style={{ color: BENCH_INK }}>S&amp;P 500</span>
                  <span>{vsSpy ? pct(r) : <>{money(p[1])} {pct(r)}</>}</span>
                </div>
              );
            })()}
          </div>
        )}
        <div className="legend desk-off">
          {[...plotSeries].sort((a, b) => b._ret - a._ret).map((c, i) => (
            <span key={i}><i className="swatch" style={{ background: methodColor(c.name, data.competitors) }} />{short(c.name)} <b className={"mono " + cls(c._ret)}>{pct(c._ret)}</b></span>
          ))}
          {plotBench && (
            <span>
              <i className="swatch" style={{ background: `repeating-linear-gradient(90deg, ${BENCH_COLOR} 0 5px, transparent 5px 9px)` }} />
              <b style={{ color: BENCH_COLOR }}>S&amp;P 500</b> <b className={"mono " + cls(plotBench._ret)}>{pct(plotBench._ret)}</b>
            </span>
          )}
          {bandRaw.length > 0 && (
            <span>
              <i className="swatch" style={{ background: "var(--ink)", opacity: 0.2 }} />
              <b>luck band</b> <span className="pmute" style={{ fontSize: ".72rem" }}>
                — the middle 80% of {data.luck.n} random {data.luck.names_per}-stock buy-and-hold portfolios; a line still inside it hasn&apos;t beaten luck.
              </span>
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <section id="field">
      <div className="eyebrow">
        <h2>The field</h2>
        <InfoButton title="The field">
          Each line is a competitor&apos;s live forward account value, plotted as cumulative return. All share one axis that starts from the common {"$" + start.toLocaleString()} origin, so they&apos;re directly comparable. The final point is re-marked to live quotes every 30s (labelled <span className="mono">live</span>); with the market closed it sits at the last tick&apos;s close. Hover to read every competitor&apos;s value on a session. Toggle <span className="mono">vs SPY</span> to divide every book by the S&amp;P 500 at each point — above the 0% line means beating the market, below means trailing it.
        </InfoButton>
        <span className="hint">{live ? "live tip" : "hover for values"} · {"$" + start.toLocaleString()} start</span>
      </div>
      {body}
      {series.length > 0 && (
        <p className="plate-cap">
          <b>Fig. 1</b> — the field since {series[0].equity_curve[0][0]}, every book from a common {"$" + start.toLocaleString()} origin; the vs SPY view divides each book by the benchmark, so above 0% = beating the market. The dashed grey line is the S&amp;P 500; the rightmost point re-marks to live quotes.
          {bandRaw.length > 0 && " The faint shaded band is the middle 80% of 200 random 5-stock buy-and-hold portfolios (dotted = their median) — a line still inside it hasn't beaten luck."}
          {" "}The strip below is each book&apos;s drawdown from its running peak — max DD, lived.
        </p>
      )}
    </section>
  );
}
