"use client";
import { money, pct, cls } from "../lib/format";
import { useModal, InfoButton } from "./ModalContext";
import { useLiveQuotes, liveMark } from "./LiveQuotes";

function Sparkline({ curve, start, liveValue }) {
  if (!curve || curve.length < 2) return null;
  // Append the live re-mark as the final point so the spark tracks the live board.
  const c = liveValue != null ? [...curve, [-1, liveValue]] : curve;
  const v = c.map((p) => p[1]);
  const mn = Math.min(...v), mx = Math.max(...v), W = 116, H = 30, pad = 2, span = (mx - mn) || 1;
  const pts = c.map((p, i) =>
    (pad + (i / (c.length - 1)) * (W - 2 * pad)).toFixed(1) + "," +
    (H - pad - ((p[1] - mn) / span) * (H - 2 * pad)).toFixed(1)
  ).join(" ");
  const up = v[v.length - 1] >= start;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={up ? "var(--up)" : "var(--down)"} strokeWidth="1.6" />
    </svg>
  );
}

// Return on the most recent tick = last completed session's move (last two curve points).
// Null when there aren't two points yet. Stays on the last close even while the board live-marks.
function lastTickRet(c) {
  const cv = c.equity_curve;
  if (!cv || cv.length < 2) return null;
  const a = cv[cv.length - 2][1], b = cv[cv.length - 1][1];
  return a ? b / a - 1 : null;
}

export default function Leaderboard({ data }) {
  const { open } = useModal();
  const { quotes, live } = useLiveQuotes();
  const m = data.methodology;
  // Figures arrive already display-scaled from build_dashboard.py; render them as-is.
  const book = "$" + data.starting_cash.toLocaleString();
  // Re-mark every book to live prices, then rank by live equity. Falls back to the stored
  // per-tick mark when a market's closed, so the order matches the published board offline.
  const ranked = data.competitors
    .map((c) => ({ ...c, _m: liveMark(c, quotes, data.starting_cash), _lt: lastTickRet(c) }))
    .sort((a, b) => b._m.equity - a._m.equity);

  function algoModal(c) {
    const tl = (c.trade_log || []).slice(-14).reverse();
    const px = (h) => { const q = quotes[h.symbol]; return q && q.price > 0 ? q.price : (h.last != null ? h.last : h.avg_price); };
    const mk = c._m || liveMark(c, quotes, data.starting_cash);
    open(
      <>
        <div className="modal-eyebrow">{c.kind}</div>
        <h3>{c.name}</h3>
        <div className="kv">
          <span className="k">Equity {mk.priced ? "(live)" : "(last tick)"}</span><span className="v">{money(mk.equity)}</span>
          <span className="k">Return</span><span className={"v " + cls(mk.ret)}>{pct(mk.ret)}</span>
          <span className="k">At last tick</span><span className="v">{money(c.final)} · {pct(c.return)}</span>
          <span className="k">Max drawdown</span><span className={"v " + cls(c.max_dd)}>{pct(c.max_dd)}</span>
          <span className="k">Trades / win rate</span><span className="v">{c.trades} · {(c.win_rate * 100).toFixed(0)}%</span>
          <span className="k">Cash</span><span className="v">{money(c.cash)}</span>
        </div>
        {c.holdings.length > 0 ? (
          <table className="tl hold">
            <thead><tr><th>holding</th><th>shares</th><th>bought</th><th>now</th><th>value</th><th>gain / loss</th></tr></thead>
            <tbody>
              {c.holdings.map((h, i) => {
                const now = px(h), shares = h.qty, value = shares * now;
                const pnl = shares * (now - h.avg_price), r = h.avg_price ? now / h.avg_price - 1 : 0;
                return (
                  <tr key={i}>
                    <td>{h.symbol}</td>
                    <td className="mono">{shares.toFixed(2)}</td>
                    <td className="mono">{money(h.avg_price)}</td>
                    <td className="mono">{money(now)}</td>
                    <td className="mono">{money(value)}</td>
                    <td className={"mono " + cls(pnl)}>{(pnl >= 0 ? "+$" : "−$") + Math.abs(pnl).toFixed(2)} ({pct(r)})</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : <p className="note">Flat — all cash.</p>}
        {(c.open_orders || []).length > 0 && (
          <div className="queued" style={{ marginTop: "12px" }}>
            <div className="queued-head">
              <span>◷ Queued — fill at next open</span>
              <span className="qn">{c.open_orders.length} resting</span>
            </div>
            {c.open_orders.map((o, i) => {
              const buy = o.side === "buy";
              return (
                <div key={i} className="qorder" style={{ borderLeft: "3px dashed " + (buy ? "var(--up)" : "var(--down)") }}>
                  <div className="qmain">
                    <span className="qside" style={{ color: buy ? "var(--up)" : "var(--down)" }}>{o.side}</span>
                    <b>{o.symbol}</b>
                    <span className="qbadge">{o.kind === "limit" && o.limit != null ? "LIMIT " + money(o.limit) : "MOO"}</span>
                  </div>
                  <span className="qsize">{buy ? money(o.dollars) : (o.qty != null ? o.qty.toFixed(2) + " sh" : "—")}</span>
                </div>
              );
            })}
            <p className="note qnote">Decided this tick, not yet filled — resting as market-on-open orders for the next session. Re-running supersedes them. Intentions, not trades.</p>
          </div>
        )}
        <p className="note"><b>Rule:</b> {c.rules}</p>
        <p className="note">Equity / return re-mark holdings to live quotes every 30s; max DD, trades and win rate are the realized per-tick record. Filled at next open + {m.slippage_bps} bps slippage, −{Math.round(m.stop_loss_pct * 100)}% stop, max {m.max_positions} positions.</p>
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
                  <td className={"mono " + (t.pnl ? cls(t.pnl) : "")}>{t.pnl ? (t.pnl >= 0 ? "+$" : "−$") + Math.abs(t.pnl).toFixed(2) : "—"}</td>
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
          The live forward paper test: every competitor trades a {book} book the same way, advanced one trading day per tick, with {m.slippage_bps} bps slippage, a −{Math.round(m.stop_loss_pct * 100)}% stop, and fills at the next open. Equity, return and the ranking re-mark each book to live quotes every 30s; with the market closed they fall back to the last tick&apos;s close. Each rule strategy&apos;s detail also shows a separate Dec–Jun backtest for context.
        </InfoButton>
        <span className="hint">{live ? "live-marked" : "last tick"} · {book} each</span>
      </div>
      <p className="cap">
        Live forward paper test — every competitor trades {book} the same way since <b>{data.period.start}</b>. Equity &amp; return are re-marked to live prices; ranking updates with them. <b>Click any row</b> for its trade log, rules, and backtest reference.
      </p>
      <div className="lead">
        <div className="row head">
          <span>#</span><span>competitor</span>
          <span className="num">equity</span><span className="num c-day">last&nbsp;tick</span><span className="num">return</span>
          <span className="num c-tr">trades</span>
          <span className="c-spark">curve</span>
        </div>
        {ranked.map((c, i) => {
          const clickable = c.clickable !== false;  // "You" is performance-only — no drill-down
          return (
          <div key={c.name} className={"row" + (clickable ? " clk" : "") + (i === 0 ? " lead-1" : "")}
               onClick={clickable ? () => algoModal(c) : undefined}
               title={clickable ? undefined : "Performance only — holdings and trades are not shown"}>
            <span className="rank">{String(i + 1).padStart(2, "0")}</span>
            <span className="name">{c.name}<span className={"tag " + c.kind}>{c.kind}</span></span>
            <span className="num">{money(c._m.equity)}</span>
            <span className={"num c-day " + (c._lt == null ? "" : cls(c._lt))}>{c._lt == null ? "—" : pct(c._lt)}</span>
            <span className={"num " + cls(c._m.ret)}>{pct(c._m.ret)}</span>
            <span className="num c-tr">{c.trades}</span>
            <span className="c-spark"><Sparkline curve={c.equity_curve} start={data.starting_cash} liveValue={c._m.priced ? c._m.equity : null} /></span>
          </div>
          );
        })}
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
