"use client";
import { useState } from "react";
import { money, pct, cls, methodColor } from "../lib/format";
import { useModal, InfoButton } from "./ModalContext";
import { named } from "../lib/names";

export function Analyst({ data }) {
  const a = data.analyst;
  if (!a) return null;
  const reg = a.regime || {};
  return (
    <div>
      <div className="eyebrow">
        <span className="n">04</span><h2>Research analyst</h2>
        <InfoButton title="Research analyst">
          A single research pass run agent-driven on the Claude Code plan: web search for current context plus Robinhood data, reconciled into one call with target weights. Every evidence row links its source.
        </InfoButton>
      </div>
      <div className="card pad">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="pickline">{a.pick} <span className={a.action}>{a.action.toUpperCase()}</span></div>
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
        {a.data_examined?.length > 0 && (
          <p className="note">Examined: {a.data_examined.map((d) => d.label).join(" · ")}</p>
        )}
        <p className="note">{a.generated_by || ""}</p>
      </div>
    </div>
  );
}

export function DecisionTrail({ data }) {
  const { open } = useModal();
  const m = data.methodology;
  const [filter, setFilter] = useState("all");
  const methods = [...new Set(data.decisions.map((d) => d.agent))];
  const colorOf = (agent) => methodColor(agent, data.competitors);
  const shown = filter === "all" ? data.decisions : data.decisions.filter((d) => d.agent === filter);
  return (
    <div>
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
          {!shown.length && <p className="pending">No decisions {filter === "all" ? "yet — fills in as ticks run." : "for this method yet."}</p>}
          {shown.map((d, i) => {
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
        </div>
      </div>
    </div>
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
            {L.note && <p className="note">{L.note}</p>}
          </>
        ) : (
          <>
            <p className="pending">{L.note || "Not connected."}</p>
            <p className="note">This panel is the headline once you trade real money — which strategy/agent placed each order, the thesis, and expected-vs-actual fill.</p>
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
    <section>
      <div className="eyebrow"><span className="n">··</span><h2>Methods &amp; sources</h2></div>
      <div className="card pad">
        <ul className="src">
          {m.sources.map((s, i) => <li key={i}><b>{s.name}.</b> {s.detail}</li>)}
          <li><b>Live prices.</b> Finnhub via the <span className="mono">/api/quotes</span> serverless function, polled every 15s, CDN-cached 15s. A public feed — separate from the Robinhood account.</li>
        </ul>
      </div>
    </section>
  );
}
