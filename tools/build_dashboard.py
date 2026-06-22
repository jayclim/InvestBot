"""Publish the dashboard's data from saved state for the Next.js web app (no API calls).

    python tools/build_dashboard.py

Writes web/public/state.json (the bake-off board) and web/public/history.json (daily close
history per symbol, for the click-through stock charts). The single-file dashboard.html twin
has been retired — web/ is the one canonical front-end.

Standings / curves / decision trail are the LIVE FORWARD paper books — every competitor
(rule strategies from state/paper_state.json, AI agents from state/agent_state.json) trades
$100 the same way, advanced one session per tick. A separate Dec–Jun walk-forward backtest
is computed for reference and shown inside each strategy's detail (not on the live board).

- Analyst card: state/analyst.json (the agent-driven report).
- Swarm panel: state/swarm.json (written by run_agents.py), else a labelled mock.
- Live panel: state/live_snapshot.json, else a not-connected panel.

Run `python run_agents.py` and `python tick.py` first to advance the books.
"""
import json
import os
import random
import datetime
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import config as cfg
from bot.engine import run_replay
from bot.metrics import summarize
from bot.portfolio import Portfolio
from bot.state import _pf_from_dict
from bot.strategy import MomentumBreakout, MeanReversion, Blended
from bot.paper import load_agents
from run import load_snapshot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGIES = [MomentumBreakout, MeanReversion, Blended]

# The real paper books are $100. The web shows them scaled to a round notional so holdings
# read in whole shares and dollars; per-share prices and percentages are untouched. The
# scaling is applied ONCE here, so every component renders one consistent scale. Display-only.
DISPLAY_SCALE = 100

RULES = {
    "momentum_breakout": "Buy a 20-day-high breakout confirmed by above-average volume; exit when price closes below its 20-day SMA. Few big winners, many small losers.",
    "mean_reversion": "Buy when RSI(14) < 30 (oversold); sell when RSI(14) > 70 (overbought). Trades less, wins more often, smaller edge.",
    "blended_momo_rsi": "Momentum breakout, but skip entries already overbought (RSI ≥ 70); exit on trend break or RSI > 75. Avoids chasing extended moves.",
}
AGENT_RULES = {
    "deep_research_analyst": "Holds the analyst's target weights; rebalanced each tick from a fresh research report (web + Robinhood data).",
    "llm_voters": "Allocates across the swarm's top vote-getters (weight ∝ vote share, capped at " + str(int(cfg.AGENT_MAX_WEIGHT*100)) + "%); rebalanced each tick.",
    "mirofish_real": "Real-MiroFish: persona agents with memory interact over rounds; consensus picks (weight ∝ vote share) rebalanced each tick.",
}
KIND = {"deep_research_analyst": "analyst", "llm_voters": "swarm", "mirofish_real": "mirofish"}


def pf_to_competitor(name, pf, kind, rules, backtest=None, marks=None):
    m = summarize(pf, cfg.STARTING_CASH)
    marks = marks or {}
    S = DISPLAY_SCALE
    c = {
        "name": name, "kind": kind,
        "final": round(m["final"] * S, 2), "return": round(m["return"], 4),
        "max_dd": round(m["max_dd"], 4), "trades": m["trades"],
        "win_rate": round(m["win_rate"], 4), "cash": round(pf.cash * S, 2), "rules": rules,
        # Account-size fields (final, cash, qty, equity_curve, trade pnl) are scaled by
        # DISPLAY_SCALE; per-share prices (avg_price, last, trade price) are not. `last` = the
        # per-tick mark (latest snapshot close); the web re-marks qty·price live and falls back
        # to `last`, so cash + Σ qty·last == final at any scale.
        "holdings": [{"symbol": s, "qty": round(p.qty * S, 4), "avg_price": round(p.avg_price, 2),
                      "last": round(marks.get(s, p.avg_price), 2)}
                     for s, p in pf.positions.items()],
        "equity_curve": [[d, round(v * S, 2)] for d, v in pf.equity_curve],
        "trade_log": [{"date": t.date, "side": t.side, "symbol": t.symbol, "qty": round(t.qty * S, 4),
                       "price": round(t.price, 2), "reason": t.reason, "pnl": round(t.pnl * S, 2)} for t in pf.trades],
    }
    if backtest:
        c["backtest"] = backtest
    return c


def load_forward_algos(names):
    p = os.path.join(ROOT, "state", "paper_state.json")
    if os.path.exists(p):
        raw = json.load(open(p))
        pfs = raw.get("portfolios", {})
        return {n: (_pf_from_dict(n, pfs[n]) if n in pfs else Portfolio(cfg.STARTING_CASH, n)) for n in names}
    return {n: Portfolio(cfg.STARTING_CASH, n) for n in names}


def build_decisions(*pf_dicts):
    feed = []
    for d in pf_dicts:
        for name, pf in d.items():
            for t in pf.trades:
                feed.append({"date": t.date, "agent": name, "symbol": t.symbol, "action": t.side,
                             "price": round(t.price, 2), "reason": t.reason, "pnl": round(t.pnl * DISPLAY_SCALE, 2)})
    feed.sort(key=lambda x: x["date"], reverse=True)
    return feed[:28]


def load_analyst(as_of):
    path = os.path.join(ROOT, "state", "analyst.json")
    if os.path.exists(path):
        a = json.load(open(path)); a["is_mock"] = False; return a
    return {"date": as_of, "pick": "—", "action": "hold", "confidence": 0.0, "is_mock": True,
            "thesis": "No analyst report yet — run a tick.", "regime": {}, "evidence": [],
            "risks": [], "data_examined": [], "note": "MOCK"}


def load_swarm(as_of):
    path = os.path.join(ROOT, "state", "swarm.json")
    if os.path.exists(path):
        s = json.load(open(path)); s["is_mock"] = False; return s
    return mock_swarm(as_of, cfg.UNIVERSE)


def mock_swarm(date, universe):
    rnd = random.Random(7)
    roster = (["DeepSeek V3.2"] * 60 + ["Gemini 2.5 Flash-Lite"] * 60 + ["Llama 4 Scout"] * 20 + ["Haiku 4.5"] * 10)
    rnd.shuffle(roster)
    pool = list(universe)
    fish = []
    for i in range(150):
        vote = "CASH" if rnd.random() < 0.09 else rnd.choice(pool)
        fish.append({"id": i + 1, "model": roster[i], "vote": vote,
                     "thesis": "Best risk/reward in the set." if vote != "CASH" else "Stay flat.",
                     "dissent": vote == "CASH"})
    tally = {}
    for f in fish:
        tally[f["vote"]] = tally.get(f["vote"], 0) + 1
    ballots = sorted(([s, n] for s, n in tally.items()), key=lambda x: x[1], reverse=True)
    models = [{"name": m, "n": roster.count(m)} for m in ["DeepSeek V3.2", "Gemini 2.5 Flash-Lite", "Llama 4 Scout", "Haiku 4.5"]]
    return {"date": date, "call": ballots[0][0], "action": "buy" if ballots[0][0] != "CASH" else "hold",
            "confidence": round(ballots[0][1] / len(fish), 3), "total_fish": len(fish),
            "ballots": ballots, "models": models, "fish": fish, "is_mock": True,
            "note": "Mock swarm — run `python run_agents.py` (with an OpenRouter key) for a live vote."}


def normalize_curves(competitors, all_dates, starting_cash):
    """Presentation-only: put every competitor on ONE shared date axis that begins at a
    $100 inception (the trading day before the first forward session), forward-filling any
    gaps. This lets all competitors plot together from a common origin even when one has a
    single tick. It does NOT touch return / max_dd / win_rate — those were already summarized
    from the true portfolio record before this runs."""
    union = sorted({d for c in competitors for d, _ in c["equity_curve"]})
    if not union:
        return
    try:
        i0 = all_dates.index(union[0])
        inception = all_dates[i0 - 1] if i0 > 0 else union[0]
    except ValueError:
        inception = union[0]
    axis = ([inception] + union) if inception != union[0] else union
    for c in competitors:
        have = {d: v for d, v in c["equity_curve"]}
        out, last = [], starting_cash
        for d in axis:
            if d in have:
                last = have[d]
            out.append([d, round(last, 2)])
        c["equity_curve"] = out


def write_history(snap):
    """Publish daily close history per symbol for the click-through stock charts — the bots'
    own snapshot data, so buy/sell markers line up exactly with what they traded on."""
    hist = {s: [[b.date, round(b.close, 2)] for b in bars] for s, bars in snap.items() if bars}
    path = os.path.join(ROOT, "web", "public", "history.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(hist, open(path, "w"))
    return len(hist)


def load_live():
    path = os.path.join(ROOT, "state", "live_snapshot.json")
    if os.path.exists(path):
        return json.load(open(path))
    return {"connected": False, "active": False, "account": "••••",
            "note": "Robinhood MCP not connected. Reconnect with /mcp to load live data."}


def main():
    snap = load_snapshot(os.path.join(ROOT, "data", "snapshot.json"))
    dates = sorted({b.date for bars in snap.values() for b in bars})
    marks = {s: bars[-1].close for s, bars in snap.items() if bars}  # latest close per symbol

    # Backtest reference (context only, shown in each strategy's detail)
    bt = run_replay(snap, STRATEGIES)
    backtest_ref = {n: {"return": round(summarize(pf, cfg.STARTING_CASH)["return"], 4),
                        "sessions": len(dates), "span": f"{dates[0]}–{dates[-1]}"} for n, pf in bt.items()}

    # LIVE forward books — the board
    strat_names = [c.name for c in STRATEGIES]
    alg_pfs = load_forward_algos(strat_names)
    competitors = [pf_to_competitor(n, alg_pfs[n], "algo", RULES.get(n, ""), backtest_ref.get(n), marks) for n in strat_names]

    _, agent_pfs = load_agents(cfg.AGENT_NAMES)
    active_agents, roster_preview = {}, []
    for n in cfg.AGENT_NAMES:
        pf = agent_pfs[n]
        if pf.equity_curve or pf.trades:
            competitors.append(pf_to_competitor(n, pf, KIND[n], AGENT_RULES[n], marks=marks))
            active_agents[n] = pf
        else:
            roster_preview.append({"name": n, "kind": KIND[n], "status": "not yet run — `python run_agents.py` to start its paper book"})
    competitors.sort(key=lambda c: c["final"], reverse=True)

    fwd_dates = sorted({d for c in competitors for d, _ in c["equity_curve"]})
    period = {"start": fwd_dates[0] if fwd_dates else dates[-1],
              "end": fwd_dates[-1] if fwd_dates else dates[-1],
              "sessions": len(fwd_dates)}

    # Put every competitor on one shared origin axis so all curves plot together (scaled, to
    # match the already-scaled equity curves above).
    normalize_curves(competitors, dates, cfg.STARTING_CASH * DISPLAY_SCALE)

    data = {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "starting_cash": round(cfg.STARTING_CASH * DISPLAY_SCALE, 2),
        "universe": list(cfg.UNIVERSE),
        "period": period,
        "backtest_span": f"{dates[0]}–{dates[-1]}",
        "competitors": competitors,
        "decisions": build_decisions(alg_pfs, active_agents),
        "analyst": load_analyst(dates[-1]),
        "swarm": load_swarm(dates[-1]),
        "live": load_live(),
        "roster_preview": roster_preview,
        "methodology": {
            "slippage_bps": cfg.SLIPPAGE_BPS, "stop_loss_pct": cfg.STOP_LOSS_PCT,
            "circuit_breaker": round(cfg.CIRCUIT_BREAKER_EQUITY * DISPLAY_SCALE, 2), "max_positions": cfg.MAX_POSITIONS,
            "position_size_pct": round(cfg.POSITION_SIZE_PCT, 3),
            "rules": {**RULES, **AGENT_RULES},
            "sources": [
                {"name": "Standings, curves, decision trail (LIVE)", "detail": "The forward paper test — every competitor trades a $100 book the same way, advanced one trading day per tick (rule strategies via tick.py / bot/engine.py; agents via run_agents.py / bot/paper.py), " + str(cfg.SLIPPAGE_BPS) + " bps slippage, −" + str(int(cfg.STOP_LOSS_PCT*100)) + "% stop. Young — it grows one session per tick."},
                {"name": "Backtest reference", "detail": "A separate Dec–Jun walk-forward backtest (" + dates[0] + "–" + dates[-1] + ", in-sample, mostly-bull) is shown inside each rule strategy's detail for context only — it is NOT the live board."},
                {"name": "Research analyst", "detail": "Agent-driven on the Claude Code plan: web_search + Robinhood data → one report (state/analyst.json) with target weights per tick. Sources link from each evidence row."},
                {"name": "Swarm vote", "detail": "Independent-voter election: 150 unique-profile cheap models (DeepSeek/Gemini/Llama/Haiku via OpenRouter) each read one shared briefing and return a single ballot; tallied in bot/swarm.py. No interaction between fish."},
                {"name": "Real-MiroFish swarm", "detail": "Social-simulation swarm (bot/mirofish.py): persona agents with memory interact over multiple rounds — each re-votes seeing its own prior view and its neighbours' latest — so a consensus forms via peer influence (the opposite of the independent swarm). Tiered cost (cheap/default/qwen); seeded from the briefing + optional world-events news."},
                {"name": "Live account", "detail": "Robinhood MCP, Agentic cash account ••••, via get_portfolio / get_equity_positions / get_equity_orders."},
                {"name": "Display scale", "detail": "The real paper books are $" + format(int(cfg.STARTING_CASH), ",") + " each; every dollar and share figure on this site is shown ×" + str(DISPLAY_SCALE) + " (a $" + format(int(cfg.STARTING_CASH * DISPLAY_SCALE), ",") + " book) so holdings read in whole shares and dollars. Per-share prices and percentages are unscaled."},
            ],
        },
    }

    # Publish data for the Next.js web app (web/ is the one canonical front-end).
    web_pub = os.path.join(ROOT, "web", "public")
    os.makedirs(web_pub, exist_ok=True)
    json.dump(data, open(os.path.join(web_pub, "state.json"), "w"))
    n_hist = write_history(snap)
    # Publish the cached daily headlines (with links) as a free static asset for the site.
    news = os.path.join(ROOT, "state", "news.json")
    n_news = 0
    if os.path.exists(news):
        nd = json.load(open(news))
        n_news = len(nd.get("items", {}))
        json.dump(nd, open(os.path.join(web_pub, "news.json"), "w"))
    a = "real" if not data["analyst"].get("is_mock") else "mock"
    sw = "live" if not data["swarm"].get("is_mock") else "mock"
    print(f"wrote web/public/state.json + history.json ({n_hist} symbols) · news={n_news} names · forward sessions={period['sessions']} · analyst={a} · swarm={sw} · competitors={len(competitors)}")


if __name__ == "__main__":
    main()
