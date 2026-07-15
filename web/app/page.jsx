"use client";
import { useEffect, useState } from "react";
import { ModalProvider, Modal } from "../components/ModalContext";
import { LiveQuotesProvider } from "../components/LiveQuotes";
import LivePrices from "../components/LivePrices";
import Leaderboard from "../components/Leaderboard";
import EquityCurves from "../components/EquityCurves";
import Graduation from "../components/Graduation";
import Swarm from "../components/Swarm";
import { Analyst, DecisionTrail, LiveAccount, Methods, Universe } from "../components/Panels";

// A fine engraved band under the headline — three interleaved arcs, banknote-style.
function Guilloche() {
  const arc = (phase, amp) => {
    let d = `M0 ${13 + phase}`;
    for (let x = 0; x < 440; x += 40) d += ` Q ${x + 20} ${13 + phase - amp} ${x + 40} ${13 + phase}`;
    return d;
  };
  return (
    <svg className="guilloche" viewBox="0 0 440 26" preserveAspectRatio="none" aria-hidden="true">
      <path d={arc(0, 10)} fill="none" stroke="currentColor" strokeWidth="0.7" />
      <path d={arc(0, -10)} fill="none" stroke="currentColor" strokeWidth="0.7" />
      <path d={arc(0, 5)} fill="none" stroke="currentColor" strokeWidth="0.5" opacity="0.6" />
      <path d={arc(0, -5)} fill="none" stroke="currentColor" strokeWidth="0.5" opacity="0.6" />
    </svg>
  );
}

export default function Page() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    fetch("/state.json", { cache: "no-store" })
      .then((r) => r.json())
      .then(setData)
      .catch(() => setErr(true));
  }, []);

  if (err) {
    return (
      <div className="wrap">
        <p className="pmute" style={{ marginTop: "30px" }}>
          Could not load <span className="mono">state.json</span>. Run <span className="mono">python3 tools/build_dashboard.py</span> from the repo root, then reload.
        </p>
      </div>
    );
  }
  if (!data) {
    return <div className="wrap"><p className="pmute" style={{ marginTop: "40px" }}>Loading…</p></div>;
  }

  const live = data.live || {};
  return (
    <ModalProvider data={data}>
      <LiveQuotesProvider data={data}>
      <div className={"livebar " + (live.active ? "live-on" : "live-off")}>
        <div className="lw">
          <span><span className="dot" />{live.active ? "Live trading — on" : "Live trading — off · paper only"}</span>
          <nav className="lvnav">
            <a href="#field">Field</a> · <a href="#standings">Standings</a> · <a href="#graduation">Graduation</a> · <a href="#analyst">Analyst</a> · <a href="#methods">Methods</a>
          </nav>
          <span className="mono">Agentic acct ••••</span>
        </div>
      </div>

      <div className="wrap">
        <header className="hd">
          <div className="kicker">Paper-trading lab · walk-forward</div>
          <h1>Every competitor starts with <em>{"$" + data.starting_cash.toLocaleString()}</em>.</h1>
          <p className="sub">Three rule-based strategies, a research analyst, and a voting swarm, each trading the same market independently. Prices update live; the board advances one trading day per tick.</p>
          <Guilloche />
          <div className="meta">
            Series <b>{data.period.start}</b> — <b>{data.period.end}</b> · {data.period.sessions} session{data.period.sessions === 1 ? "" : "s"}
            {data.backtest_span ? ` · backtest ref ${data.backtest_span}` : ""} · generated {data.generated_at}
          </div>
        </header>

        <EquityCurves data={data} />
        <Leaderboard data={data} />
        <Graduation data={data} />
        <LivePrices data={data} />
        <Swarm data={data} />

        <Analyst data={data} />
        <DecisionTrail data={data} />

        <LiveAccount data={data} />
        <Methods data={data} />
        <Universe data={data} />

        <footer>
          <div>Bake-off state regenerated each tick by <span className="mono">tools/build_dashboard.py</span>; live prices via <span className="mono">/api/quotes</span> (Finnhub).</div>
          <div className="note">Standings are the live forward paper test, extended by one session each tick, all on fake money. No real orders are placed.</div>
        </footer>
      </div>

      <Modal />
      </LiveQuotesProvider>
    </ModalProvider>
  );
}
