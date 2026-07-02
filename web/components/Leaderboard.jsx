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

// Gain/loss since the last trading day, as a dollar amount (display-scaled) and a percent.
// Uses the live-marked equity vs the PRIOR session's close, so market-open shows today's move
// so far and market-closed shows the last completed session's move — mirroring the equity chart's
// live/day split. Null until there are two points. `m` is the competitor's liveMark.
function dayChange(c, m) {
  // The "You" line publishes no holdings, so the frontend can't live-price it — its only number
  // would be a stale last-tick move, which misreads as "today." Leave it blank; the live-markable
  // competitors still show a real today gain/loss.
  if (c.kind === "me") return null;
  const cv = c.equity_curve;
  if (!cv || cv.length < 2) return null;
  const todayET = new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
  const lastIsToday = cv[cv.length - 1][0] === todayET;
  // Prior close = the last stored point, unless it's already today's (a tick ran) or the board is
  // offline and m.equity IS that last close — then step back one so we compare against yesterday.
  const base = (m.priced && !lastIsToday) ? cv[cv.length - 1][1] : cv[cv.length - 2][1];
  return base ? { amt: m.equity - base, ret: m.equity / base - 1 } : null;
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
    .map((c) => { const _m = liveMark(c, quotes, data.starting_cash); return { ...c, _m, _lt: dayChange(c, _m) }; })
    .sort((a, b) => b._m.equity - a._m.equity);

  function algoModal(c) {
    const tl = (c.trade_log || []).slice(-14).reverse();
    const px = (h) => { const q = quotes[h.symbol]; return q && q.price > 0 ? q.price : (h.last != null ? h.last : h.avg_price); };
    // Per-stock today gain/loss off the live quote's prevClose. Shares bought today move from
    // their fill price, not yesterday's close (Robinhood-style). Null without a real quote.
    const todayET = new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
    const dayPnl = (h) => {
      const q = quotes[h.symbol];
      if (!(q && q.price > 0 && q.prevClose > 0)) return null;
      const boughtToday = h.filled_at &&
        new Date(h.filled_at).toLocaleDateString("en-CA", { timeZone: "America/New_York" }) === todayET;
      const base = boughtToday ? h.avg_price : q.prevClose;
      return base > 0 ? { amt: h.qty * (q.price - base), ret: q.price / base - 1 } : null;
    };
    const mk = c._m || liveMark(c, quotes, data.starting_cash);
    open(
      <>
        <div className="modal-eyebrow">{c.kind}</div>
        <h3>{c.name}</h3>
        {c.note && <p className="note livenote">{c.note}</p>}
        <div className="kv">
          <span className="k">Equity {mk.priced ? "(live)" : "(last close)"}</span><span className="v">{money(mk.equity)}</span>
          <span className="k">Return</span><span className={"v " + cls(mk.ret)}>{pct(mk.ret)}</span>
          <span className="k">At last close</span><span className="v">{money(c.final)} · {pct(c.return)}</span>
          <span className="k">Max drawdown</span><span className={"v " + cls(c.max_dd)}>{pct(c.max_dd)}</span>
          <span className="k">Trades / win rate</span><span className="v">{c.trades} · {(c.win_rate * 100).toFixed(0)}%</span>
          <span className="k">Cash</span><span className="v">{money(c.cash)}</span>
        </div>
        {c.holdings.length > 0 ? (
          <table className="tl hold">
            <thead><tr><th>holding</th><th>shares</th><th>bought</th><th>now</th><th>value</th><th>{live ? "today" : "last day"}</th><th>gain / loss</th></tr></thead>
            <tbody>
              {c.holdings.map((h, i) => {
                const now = px(h), shares = h.qty, value = shares * now;
                const pnl = shares * (now - h.avg_price), r = h.avg_price ? now / h.avg_price - 1 : 0;
                const d = dayPnl(h);
                return (
                  <tr key={i}>
                    <td>{h.symbol}</td>
                    <td className="mono">{shares.toFixed(2)}</td>
                    <td className="mono">{money(h.avg_price)}{h.filled_at && <div className="pmute" style={{ fontSize: "11px" }}>{new Date(h.filled_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" })} ET</div>}</td>
                    <td className="mono">{money(now)}</td>
                    <td className="mono">{money(value)}</td>
                    <td className={"mono " + (d ? cls(d.amt) : "")}>{d ? <>{(d.amt >= 0 ? "+$" : "−$") + Math.abs(d.amt).toFixed(2)}<div className="pmute" style={{ fontSize: "11px" }}>{pct(d.ret)}</div></> : "—"}</td>
                    <td className={"mono " + cls(pnl)}>{(pnl >= 0 ? "+$" : "−$") + Math.abs(pnl).toFixed(2)}<div className="pmute" style={{ fontSize: "11px" }}>{pct(r)}</div></td>
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
              <span className="qn">{(mk.fills?.size)
                ? `${mk.fills.size} filled live · ${c.open_orders.length - mk.fills.size} resting`
                : `${c.open_orders.length} resting`}</span>
            </div>
            {c.open_orders.map((o, i) => {
              const buy = o.side === "buy";
              const simmed = mk.fills?.has(i);
              return (
                <div key={i} className="qorder" style={{ borderLeft: "3px " + (simmed ? "solid" : "dashed") + " " + (buy ? "var(--up)" : "var(--down)") }}>
                  <div className="qmain">
                    <span className="qside" style={{ color: buy ? "var(--up)" : "var(--down)" }}>{o.side}</span>
                    <b>{o.symbol}</b>
                    <span className="qbadge">{o.kind === "limit" && o.limit != null ? "LIMIT " + money(o.limit) : "MOO"}</span>
                    {simmed && <span className="qbadge">filled @ open</span>}
                  </div>
                  <span className="qsize">{buy ? money(o.dollars) : (o.qty != null ? o.qty.toFixed(2) + " sh" : "—")}</span>
                </div>
              );
            })}
            <p className="note qnote">Decided last tick as market-on-open orders. Ones marked <b>filled @ open</b> have seen a session open since — the live equity above already counts them at the day&apos;s open price; the next tick records them officially. The rest are resting (re-running supersedes them).</p>
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
          The live forward paper test: every competitor trades a {book} book the same way, advanced one trading day per tick, with {m.slippage_bps} bps slippage, a −{Math.round(m.stop_loss_pct * 100)}% stop, and fills at the next open. Equity, return and the ranking re-mark each book to live quotes every 30s; with the market closed they fall back to the last session&apos;s close. The <b>today</b> column is each book&apos;s gain/loss since the last trading day — live intraday, or the last completed session when the market&apos;s closed. Each rule strategy&apos;s detail also shows a separate Dec–Jun backtest for context.
        </InfoButton>
        <span className="hint">{live ? "live-marked" : "last close"} · {book} each</span>
      </div>
      <p className="cap">
        Live forward paper test — every competitor trades {book} the same way since <b>{data.period.start}</b>. Equity &amp; return are re-marked to live prices; ranking updates with them. <b>Click any row</b> for its trade log, rules, and backtest reference.
      </p>
      <div className="lead">
        <div className="row head">
          <span>#</span><span>competitor</span>
          <span className="num">equity</span><span className="num c-day">{live ? "today" : "last day"}</span><span className="num">return</span>
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
            <span className={"num c-day " + (c._lt == null ? "" : cls(c._lt.ret))}>
              {c._lt == null ? "—" : <>
                <span>{(c._lt.amt >= 0 ? "+" : "−") + money(Math.abs(c._lt.amt))}</span>
                <span className="d-sub">{pct(c._lt.ret)}</span>
              </>}
            </span>
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
