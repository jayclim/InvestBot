"use client";
import { useState } from "react";
import { money, pct, cls, methodColor } from "../lib/format";
import { useModal, InfoButton } from "./ModalContext";
import { useLiveQuotes, simFillPrice } from "./LiveQuotes";
import { named } from "../lib/names";

// One analyst chart spec → an "Exhibit" figure, drawn natively so it matches the site.
// Specs come from state/analyst.json `charts`: {type:"bars"|"line", title, unit, source, items|points}.
function Exhibit({ ch, i }) {
  const letter = String.fromCharCode(65 + i);
  const fmt = (v) =>
    ch.unit === "%" ? v.toFixed(Math.abs(v) >= 10 ? 0 : 1) + "%"
    : ch.unit === "$" ? "$" + Number(v).toFixed(Math.abs(v) >= 100 ? 0 : 2)
    : String(v);
  let body = null;
  if (ch.type === "bars" && ch.items?.length) {
    const items = ch.items.slice(0, 12);
    const mx = Math.max(...items.map((d) => Math.abs(d.value)), 1e-9);
    const W = 420, rh = 22, lab = 92, val = 56, H = items.length * rh + 6;
    body = (
      <svg className="chart" viewBox={`0 0 ${W} ${H}`}>
        {items.map((d, k) => {
          const w = Math.max((Math.abs(d.value) / mx) * (W - lab - val - 10), 1);
          const y0 = 3 + k * rh;
          return (
            <g key={k}>
              <text x={lab - 8} y={y0 + 14.5} textAnchor="end" fontFamily="IBM Plex Mono" fontSize="11" fill="var(--ink)">{d.label}</text>
              <rect x={lab} y={y0 + 4} width={w} height={13} fill={d.value < 0 ? "var(--down)" : "var(--signal)"} opacity="0.85" />
              <text x={lab + w + 6} y={y0 + 14.5} fontFamily="IBM Plex Mono" fontSize="10.5" fill="var(--muted)">{fmt(d.value)}</text>
            </g>
          );
        })}
      </svg>
    );
  } else if (ch.type === "line" && ch.points?.length >= 2) {
    const pts = ch.points.slice(0, 64);
    const W = 420, H = 150, L = 8, R = 62, T = 10, B = 20;
    const ys = pts.map((p) => p[1]);
    let lo = Math.min(...ys), hi = Math.max(...ys);
    const padY = (hi - lo) * 0.1 || 1; lo -= padY; hi += padY;
    const x = (k) => L + (k / (pts.length - 1)) * (W - L - R);
    const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
    const last = pts[pts.length - 1];
    body = (
      <svg className="chart" viewBox={`0 0 ${W} ${H}`}>
        {[lo + padY, hi - padY].map((v, k) => (
          <g key={k}>
            <line x1={L} y1={y(v)} x2={W - R} y2={y(v)} stroke="var(--line-2)" />
            <text x={W - R + 7} y={y(v) + 3.5} fontFamily="IBM Plex Mono" fontSize="9.5" fill="var(--muted)">{fmt(v)}</text>
          </g>
        ))}
        <polyline points={pts.map((p, k) => x(k).toFixed(1) + "," + y(p[1]).toFixed(1)).join(" ")} fill="none" stroke="var(--signal)" strokeWidth="1.8" strokeLinejoin="round" />
        <circle cx={x(pts.length - 1)} cy={y(last[1])} r="2.6" fill="var(--signal)" />
        <text x={x(pts.length - 1) + 7} y={y(last[1]) + 3.5} fontFamily="IBM Plex Mono" fontSize="10.5" fontWeight="600" fill="var(--signal)">{fmt(last[1])}</text>
        <text x={L} y={H - 6} fontFamily="IBM Plex Mono" fontSize="9.5" fill="var(--muted)">{pts[0][0]}</text>
        <text x={W - R} y={H - 6} textAnchor="end" fontFamily="IBM Plex Mono" fontSize="9.5" fill="var(--muted)">{last[0]}</text>
      </svg>
    );
  }
  if (!body) return null;
  return (
    <figure className="exh">
      {body}
      <figcaption className="exh-cap"><b>Exhibit {letter}</b> — {ch.title}{ch.source ? <span> · {ch.source}</span> : null}</figcaption>
    </figure>
  );
}

export function Analyst({ data }) {
  const a = data.analyst;
  if (!a) return null;
  const reg = a.regime || {};
  const ref = a.reflection;
  const col = methodColor("deep_research_analyst", data.competitors);
  // The analyst's own fills, newest batch first — the trades behind this tick's thesis.
  const aTrades = (data.decisions || []).filter((d) => d.agent === "deep_research_analyst");
  const tickTrades = aTrades.length ? aTrades.filter((d) => d.date === aTrades[0].date) : [];
  return (
    <section id="analyst">
      <div className="eyebrow">
        <span className="n">04</span><h2>Research analyst</h2>
        <InfoButton title="Research analyst">
          A single research pass run agent-driven on the Claude Code plan: web search for current context plus Robinhood data, reconciled into one call with target weights. Every evidence row links its source.
        </InfoButton>
      </div>
      <div className="card pad">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          {/* action is usually buy/hold/sell, but some ticks carry a whole thesis sentence —
              drop those to quiet body type instead of shouting them in display caps */}
          <div className={"pickline" + ((String(a.pick) + a.action).length > 48 ? " long" : "")}>{a.pick} <span className={a.action}>{a.action.length <= 6 ? a.action.toUpperCase() : a.action}</span></div>
          <span className={"badge " + (a.is_mock ? "mock" : "live")}>{a.is_mock ? "mock" : "agent-driven"}</span>
        </div>
        {a.sizing && <div style={{ margin: "6px 0" }}><span className="chip">{a.sizing}</span></div>}
        {a.framework && <p className="note" style={{ marginTop: "4px" }}><b>Method:</b> {a.framework}</p>}
        <div className="mono" style={{ fontSize: ".74rem", color: "var(--muted)" }}>
          conviction {(a.confidence * 100).toFixed(0)}%{a.as_of ? " · as of " + a.as_of : ""}
        </div>
        <div className="conf"><i style={{ width: (a.confidence * 100).toFixed(0) + "%" }} /></div>
        {reg.label && (
          <p className="note"><b>Regime — {reg.label}:</b> {reg.note} {reg.source && <a href={reg.source}>source ↗</a>}</p>
        )}
        <p style={{ fontSize: ".93rem" }}>{a.thesis}</p>
        {(a.charts || []).length > 0 && (
          <div className="exhibits">
            {a.charts.slice(0, 3).map((ch, i) => <Exhibit key={i} ch={ch} i={i} />)}
          </div>
        )}
        {tickTrades.length > 0 && (
          <>
            <p className="note" style={{ marginTop: "12px" }}><b>Trades placed</b> <span className="mono" style={{ fontWeight: 400 }}>· {tickTrades[0].date}</span></p>
            <ul className="atrades">
              {tickTrades.map((t, i) => {
                const why = a.rationale?.[t.symbol];
                const long = why && why.length > 140;
                return (
                  <li key={i} style={{ borderLeft: "3px solid " + col }}>
                    <div className="atrade-row">
                      <span className="aact" style={{ color: t.action === "buy" ? "var(--up)" : "var(--down)" }}>{t.action}</span>
                      <b>{t.symbol}</b>
                      <span className="mono apx">{money(t.price)}</span>
                      <span className="areason">{t.reason.replace(/^analyst:\s*/, "")}</span>
                      {t.pnl ? <span className={"mono " + cls(t.pnl)}>{(t.pnl >= 0 ? "+" : "") + t.pnl.toFixed(2)}</span> : <span />}
                    </div>
                    {why && (long ? (
                      <details className="awhy">
                        <summary><span className="chev">▸</span> Why {t.symbol}?</summary>
                        <p>{why}</p>
                      </details>
                    ) : (
                      <p className="awhy-line">{why}</p>
                    ))}
                  </li>
                );
              })}
            </ul>
          </>
        )}
        {a.evidence?.length > 0 && (
          <ul className="ev">
            {a.evidence.map((e, i) => (
              <li key={i}><span>{e.point}</span><span>{String(e.source).startsWith("http") ? <a href={e.source}>source ↗</a> : e.source}</span></li>
            ))}
          </ul>
        )}
        {a.risks?.length > 0 && (
          <>
            <p className="note" style={{ marginTop: "12px" }}><b>Key risks</b></p>
            <ul className="risks">{a.risks.map((r, i) => <li key={i}>{r}</li>)}</ul>
          </>
        )}
        {ref && (
          <div className="lookback">
            <p className="note" style={{ marginTop: "14px" }}><b>Looking back</b>{ref.as_of ? <span className="mono" style={{ fontWeight: 400 }}> · on {ref.as_of}</span> : ""}</p>
            {ref.looking_back && <p style={{ fontSize: ".9rem", margin: "4px 0 8px" }}>{ref.looking_back}</p>}
            {(ref.worked?.length > 0 || ref.missed?.length > 0) && (
              <div className="lb-cols">
                {ref.worked?.length > 0 && (
                  <div><div className="lb-h" style={{ color: "var(--up)" }}>Worked</div>
                    <ul>{ref.worked.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
                )}
                {ref.missed?.length > 0 && (
                  <div><div className="lb-h" style={{ color: "var(--down)" }}>Missed</div>
                    <ul>{ref.missed.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
                )}
              </div>
            )}
            {ref.adjustment && <p className="note" style={{ marginTop: "8px" }}><b>Adjusting this tick:</b> {ref.adjustment}</p>}
          </div>
        )}
        {a.data_examined?.length > 0 && (
          <p className="note">Examined: {a.data_examined.map((d) => d.label).join(" · ")}</p>
        )}
        <p className="note">{a.generated_by || ""}</p>
      </div>
    </section>
  );
}

export function DecisionTrail({ data }) {
  const { open } = useModal();
  const { quotes } = useLiveQuotes();
  const m = data.methodology;
  const [filter, setFilter] = useState("all");
  const methods = [...new Set(data.decisions.map((d) => d.agent))];
  const colorOf = (agent) => methodColor(agent, data.competitors);
  const shown = filter === "all" ? data.decisions : data.decisions.filter((d) => d.agent === filter);
  // Orders placed this tick but not yet filled — resting as market-on-open for the next session.
  const queued = data.competitors.flatMap((c) => (c.open_orders || []).map((o) => ({ ...o, agent: c.name })));
  const qShown = filter === "all" ? queued : queued.filter((o) => o.agent === filter);
  // Bucket into days (decisions arrive newest-first); coalesces by date even if interleaved.
  const byDay = [];
  const dayIdx = {};
  shown.forEach((d) => {
    if (dayIdx[d.date] === undefined) { dayIdx[d.date] = byDay.length; byDay.push([d.date, []]); }
    byDay[dayIdx[d.date]][1].push(d);
  });
  return (
    <section>
      <div className="eyebrow">
        <span className="n">05</span><h2>Decision trail</h2>
        <InfoButton title="Decision trail">
          Every buy/sell across the live forward books, newest first, with the rule or reason behind it. Each row is colour-coded by method; use the chips to filter to one. Click a row for the full record.
        </InfoButton>
        <span className="hint">most recent · click for detail</span>
      </div>
      <div className="card pad">
        {methods.length > 1 && (
          <div className="trail-filters">
            <button className={"tf" + (filter === "all" ? " on" : "")} onClick={() => setFilter("all")}>
              all <span className="tf-n">{data.decisions.length}</span>
            </button>
            {methods.map((mth) => {
              const col = colorOf(mth);
              const n = data.decisions.filter((d) => d.agent === mth).length;
              const on = filter === mth;
              return (
                <button
                  key={mth}
                  className={"tf" + (on ? " on" : "")}
                  style={on ? { background: col, borderColor: col, color: "#fff" } : { borderColor: col, color: col }}
                  onClick={() => setFilter(on ? "all" : mth)}
                >
                  <i className="tf-dot" style={{ background: on ? "#fff" : col }} />{mth} <span className="tf-n">{n}</span>
                </button>
              );
            })}
          </div>
        )}
        <div className="feed">
          {qShown.length > 0 && (() => {
            const nFilled = qShown.filter((o) => simFillPrice(o, quotes[o.symbol]) != null).length;
            return (
            <div className="queued">
              <div className="queued-head">
                <span>◷ Queued — fill at next open</span>
                <span className="qn">{nFilled ? `${nFilled} filled live · ${qShown.length - nFilled} resting` : `${qShown.length} resting`}</span>
              </div>
              {qShown.map((o, i) => {
                const col = colorOf(o.agent);
                const buy = o.side === "buy";
                const fillPx = simFillPrice(o, quotes[o.symbol]);
                return (
                  <div key={i} className="qorder" style={{ borderLeft: "3px " + (fillPx != null ? "solid" : "dashed") + " " + col }}>
                    <div className="qmain">
                      <span className="qside" style={{ color: buy ? "var(--up)" : "var(--down)" }}>{o.side}</span>
                      <b>{o.symbol}</b>
                      <span className="qbadge">{o.kind === "limit" && o.limit != null ? "LIMIT " + money(o.limit) : "MOO"}</span>
                      {fillPx != null && <span className="qbadge">filled @ {money(fillPx)}</span>}
                      <span className="qwho" style={{ color: col }}>{o.agent}</span>
                    </div>
                    <span className="qsize">{buy ? money(o.dollars) : (o.qty != null ? o.qty.toFixed(2) + " sh" : "—")}</span>
                  </div>
                );
              })}
              <p className="note qnote">Decided last tick as market-on-open orders. Ones marked <b>filled</b> have seen a session open since — the standings already count them at the open price; the next tick records them officially. The rest are resting (re-running supersedes them). Intentions, not trades.</p>
            </div>
            );
          })()}
          {!shown.length && <p className="pending">No filled decisions {filter === "all" ? "yet — fills in as ticks run." : "for this method yet."}</p>}
          {byDay.map(([day, rows], di) => (
            <details key={day} className="day" open={di === 0}>
              <summary className="day-sum">
                <span className="day-date">{day}</span>
                <span className="day-n">{rows.length} {rows.length === 1 ? "trade" : "trades"}</span>
              </summary>
              {rows.map((d, i) => {
                const col = colorOf(d.agent);
                return (
              <div
                key={i}
                className="dec"
                style={{ borderLeft: "3px solid " + col, paddingLeft: "11px" }}
                onClick={() => open(
                  <>
                    <div className="modal-eyebrow">{d.date} · {d.agent}</div>
                    <h3 style={{ color: d.action === "buy" ? "var(--up)" : "var(--down)" }}>{d.action.toUpperCase()} {d.symbol}</h3>
                    <div className="kv">
                      <span className="k">Method</span><span className="v" style={{ color: col }}>{d.agent}</span>
                      <span className="k">Fill price</span><span className="v">{money(d.price)}</span>
                      <span className="k">Realized P&amp;L</span><span className={"v " + (d.pnl ? cls(d.pnl) : "")}>{d.pnl ? (d.pnl >= 0 ? "+" : "") + d.pnl.toFixed(2) : "—"}</span>
                    </div>
                    <p><b>Why:</b> {d.reason}</p>
                    <p className="note">Decided on the prior close, filled at the next open + {m.slippage_bps} bps slippage.</p>
                  </>
                )}
              >
                <div className="when">{d.date}</div>
                <div>
                  <span className="act" style={{ color: d.action === "buy" ? "var(--up)" : "var(--down)" }}>{d.action}</span> <b>{d.symbol}</b> <span className="who" style={{ color: col }}>{d.agent}</span>
                  <div className="why">{d.reason}{d.pnl ? <> <span className={"mono " + cls(d.pnl)}>({d.pnl >= 0 ? "+" : ""}{d.pnl.toFixed(2)})</span></> : ""}</div>
                </div>
                <span className="chev">›</span>
              </div>
                );
              })}
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function LiveAccount({ data }) {
  const L = data.live || {};
  return (
    <section>
      <div className="eyebrow">
        <span className="n">06</span><h2>Live account</h2>
        <InfoButton title="Live account">
          When the Robinhood MCP is connected, this pulls real balance, positions, and agent-placed orders from the Agentic cash account ••••. It stays empty until you trade real money. (Live prices above come from a public feed, not this account.)
        </InfoButton>
        <span className="hint">Robinhood · Agentic ••••</span>
      </div>
      <div className="card pad">
        {L.connected ? (
          <>
            <div className="kv">
              <span className="k">Portfolio value</span><span className="v">{money(L.portfolio_value || 0)}</span>
              <span className="k">Buying power</span><span className="v">{money(L.buying_power || 0)}</span>
              <span className="k">Cash</span><span className="v">{money(L.cash || 0)}</span>
            </div>
            <table className="tl">
              <thead><tr><th>symbol</th><th>qty</th><th>avg</th></tr></thead>
              <tbody>
                {(L.positions || []).length === 0 ? (
                  <tr><td colSpan="3" className="pending">no open positions</td></tr>
                ) : (
                  L.positions.map((p, i) => <tr key={i}><td>{p.symbol}</td><td className="mono">{p.qty}</td><td className="mono">{money(p.avg_price)}</td></tr>)
                )}
              </tbody>
            </table>
            {(L.orders || []).length > 0 && (
              <>
                <p className="note" style={{ marginBottom: 0 }}><b>Agent-placed orders</b> (filled)</p>
                <table className="tl">
                  <thead><tr><th>date</th><th>side</th><th>sym</th><th>fill</th><th>size</th></tr></thead>
                  <tbody>
                    {L.orders.map((o, i) => (
                      <tr key={i}>
                        <td>{o.date}</td>
                        <td className="mono" style={{ color: o.side === "buy" ? "var(--up)" : "var(--down)" }}>{o.side}</td>
                        <td>{o.symbol}</td>
                        <td className="mono">{money(o.avg_price)}</td>
                        <td className="mono">{money(o.dollars)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
            {L.note && <p className="note">{L.note}</p>}
          </>
        ) : (
          <>
            <p className="pending">{L.note || "Not connected."}</p>
            <p className="note">This panel becomes the focus once you trade real money: which strategy/agent placed each order, the thesis, and expected-vs-actual fill.</p>
          </>
        )}
      </div>
    </section>
  );
}

export function Universe({ data }) {
  const { openStock } = useModal();
  const u = data.universe || [];
  if (!u.length) return null;
  return (
    <section>
      <div className="eyebrow">
        <span className="n">··</span><h2>Stock pool</h2>
        <InfoButton title="Stock pool">
          The {u.length}-name universe every competitor screens and trades from — high-beta single stocks plus leveraged/inverse ETFs (defined in <span className="mono">bot/config.py</span>). Click any ticker for its chart, buy/sell markers, and news.
        </InfoButton>
        <span className="hint">{u.length} symbols · click any</span>
      </div>
      <div className="card pad">
        <div className="pool">
          {u.map((s) => (
            <span
              key={s}
              className="chip clk"
              role="button"
              tabIndex={0}
              onClick={() => openStock(s)}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openStock(s); } }}
            >{named(s)}</span>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Methods({ data }) {
  const m = data.methodology;
  return (
    <section id="methods">
      <div className="eyebrow"><span className="n">··</span><h2>Methods &amp; sources</h2></div>
      <div className="card pad">
        <ul className="src">
          {m.sources.map((s, i) => <li key={i}><b>{s.name}.</b> {s.detail}</li>)}
          <li><b>Live prices.</b> Finnhub via the <span className="mono">/api/quotes</span> serverless function, polled every 30s, CDN-cached 30s. A public feed — separate from the Robinhood account.</li>
        </ul>
      </div>
    </section>
  );
}
