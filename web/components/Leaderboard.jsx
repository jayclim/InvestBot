"use client";
import { money, pct, cls } from "../lib/format";
import { useModal, InfoButton } from "./ModalContext";

function Sparkline({ curve, start }) {
  if (!curve || curve.length < 2) return null;
  const v = curve.map((p) => p[1]);
  const mn = Math.min(...v), mx = Math.max(...v), W = 116, H = 30, pad = 2, span = (mx - mn) || 1;
  const pts = curve.map((p, i) =>
    (pad + (i / (curve.length - 1)) * (W - 2 * pad)).toFixed(1) + "," +
    (H - pad - ((p[1] - mn) / span) * (H - 2 * pad)).toFixed(1)
  ).join(" ");
  const up = v[v.length - 1] >= start;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={up ? "var(--up)" : "var(--down)"} strokeWidth="1.6" />
    </svg>
  );
}

export default function Leaderboard({ data }) {
  const { open } = useModal();
  const m = data.methodology;
  const ranked = [...data.competitors].sort((a, b) => b.final - a.final);

  function algoModal(c) {
    const tl = (c.trade_log || []).slice(-14).reverse();
    const hold = c.holdings.length ? c.holdings.map((h) => `${h.symbol} ${h.qty}@${money(h.avg_price)}`).join(", ") : "flat";
    open(
      <>
        <div className="modal-eyebrow">{c.kind}</div>
        <h3>{c.name}</h3>
        <div className="kv">
          <span className="k">Final equity</span><span className="v">{money(c.final)}</span>
          <span className="k">Return</span><span className={"v " + cls(c.return)}>{pct(c.return)}</span>
          <span className="k">Max drawdown</span><span className={"v " + cls(c.max_dd)}>{pct(c.max_dd)}</span>
          <span className="k">Trades / win rate</span><span className="v">{c.trades} · {(c.win_rate * 100).toFixed(0)}%</span>
          <span className="k">Cash / holdings</span><span className="v">{money(c.cash)} · {hold}</span>
        </div>
        <p className="note"><b>Rule:</b> {c.rules}</p>
        <p className="note">Live forward book — filled at next open + {m.slippage_bps} bps slippage, −{Math.round(m.stop_loss_pct * 100)}% stop, max {m.max_positions} positions.</p>
        {c.backtest && (
          <p className="note"><b>Backtest reference ({c.backtest.span}):</b> {pct(c.backtest.return)} over {c.backtest.sessions} sessions — context only, not the live board.</p>
        )}
        {tl.length > 0 && (
          <table className="tl">
            <thead><tr><th>date</th><th>side</th><th>sym</th><th>price</th><th>P&amp;L</th></tr></thead>
            <tbody>
              {tl.map((t, i) => (
                <tr key={i}>
                  <td>{t.date}</td>
                  <td className="mono" style={{ color: t.side === "buy" ? "var(--up)" : "var(--down)" }}>{t.side}</td>
                  <td>{t.symbol}</td>
                  <td className="mono">{money(t.price)}</td>
                  <td className={"mono " + (t.pnl ? cls(t.pnl) : "")}>{t.pnl ? (t.pnl >= 0 ? "+" : "") + t.pnl.toFixed(2) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </>
    );
  }

  return (
    <section>
      <div className="eyebrow">
        <span className="n">01</span>
        <h2>Standings</h2>
        <InfoButton title="Standings">
          The live forward paper test: every competitor trades a $100 book the same way, advanced one trading day per tick, with {m.slippage_bps} bps slippage, a −{Math.round(m.stop_loss_pct * 100)}% stop, and fills at the next open. It&apos;s young, so early numbers are noisy. Each rule strategy&apos;s detail also shows a separate Dec–Jun backtest for context.
        </InfoButton>
        <span className="hint">${data.starting_cash.toFixed(0)} each</span>
      </div>
      <p className="cap">
        Live forward paper test — every competitor trades $100 the same way since <b>{data.period.start}</b>. Young record; it grows one session per tick. <b>Click any row</b> for its trade log, rules, and backtest reference.
      </p>
      <div className="lead">
        <div className="row head">
          <span>#</span><span>competitor</span>
          <span className="num">equity</span><span className="num">return</span>
          <span className="num c-dd">max&nbsp;DD</span><span className="num c-tr">trades</span>
          <span className="c-spark">curve</span>
        </div>
        {ranked.map((c, i) => (
          <div key={c.name} className={"row clk" + (i === 0 ? " lead-1" : "")} onClick={() => algoModal(c)}>
            <span className="rank">{String(i + 1).padStart(2, "0")}</span>
            <span className="name">{c.name}<span className={"tag " + c.kind}>{c.kind}</span></span>
            <span className="num">{money(c.final)}</span>
            <span className={"num " + cls(c.return)}>{pct(c.return)}</span>
            <span className={"num c-dd " + cls(c.max_dd)}>{pct(c.max_dd)}</span>
            <span className="num c-tr">{c.trades}</span>
            <span className="c-spark"><Sparkline curve={c.equity_curve} start={data.starting_cash} /></span>
          </div>
        ))}
        {(data.roster_preview || []).map((p) => (
          <div key={p.name} className="row">
            <span className="rank">··</span>
            <span className="name">{p.name}<span className={"tag " + p.kind}>{p.kind}</span></span>
            <span className="pending" style={{ gridColumn: "3 / -1" }}>{p.status}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
