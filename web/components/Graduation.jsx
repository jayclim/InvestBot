"use client";
import { pct } from "../lib/format";
import { InfoButton } from "./ModalContext";

// The standing rule: no strategy runs real money at scale until it clears all four gates on
// its own live forward book. `data.graduation` is absent on older state.json — guard for it.
export default function Graduation({ data }) {
  const g = data.graduation;
  if (!g || !g.rows || !g.rows.length) return null;
  const crit = g.criteria || [];
  const passedN = g.rows.filter((r) => r.passed).length;
  // criteria labels read "≥60 sessions" / "≥20 decisions" — pull the threshold back out for the "x/N" cells.
  const threshold = (key) => {
    const c = crit.find((x) => x.key === key);
    const m = c && String(c.label).match(/\d+/);
    return m ? m[0] : "?";
  };

  return (
    <section id="graduation">
      <div className="eyebrow">
        <h2>Graduation bar</h2>
        <InfoButton title="Graduation bar">
          Four gates a paper strategy must clear on its own live forward book before it&apos;s eligible to
          run real money at scale: at least 60 sessions of history, at least 20 realized decisions, a max
          drawdown better than −20%, and a positive excess return vs the S&amp;P 500 — otherwise the index
          beats it by doing nothing. The real-money <span className="mono">run-robin</span> allocation
          (<span className="mono">state/robin_alloc.json</span>) stays limited to strategies that clear
          all four; nothing here changes automatically when a row turns green.
        </InfoButton>
        <span className="hint">{passedN} / {g.rows.length} graduated</span>
      </div>
      <p className="cap">
        The standing rule: no strategy trades real money at scale until every gate clears on the live
        forward book — <b>{passedN} of {g.rows.length}</b> graduated so far.
      </p>
      <div className="card pad">
        <table className="tl">
          <thead>
            <tr>
              <th>competitor</th>
              {crit.map((c) => <th key={c.key} title={c.detail}>{c.label}</th>)}
              <th>verdict</th>
            </tr>
          </thead>
          <tbody>
            {g.rows.map((r) => (
              <tr key={r.name}>
                <td>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: "4px" }}>
                    <span>{r.name}</span>
                    <span className={"tag " + r.kind}>{r.kind}</span>
                  </div>
                </td>
                {crit.map((c) => {
                  const ok = !!(r.checks && r.checks[c.key]);
                  let val;
                  if (c.key === "sessions") val = `${r.sessions}/${threshold("sessions")}`;
                  else if (c.key === "decisions") val = `${r.decisions}/${threshold("decisions")}`;
                  else if (c.key === "max_dd") val = pct(r.max_dd);
                  else if (c.key === "excess") val = pct(r.excess);
                  return (
                    <td key={c.key}>
                      <span style={{ color: ok ? "var(--up)" : "var(--down)" }}>{ok ? "✓" : "✗"}</span>
                      <div className="mono" style={{ fontSize: ".72rem", color: "var(--muted)" }}>{val}</div>
                    </td>
                  );
                })}
                <td>
                  <span className={"tag" + (r.passed ? " live" : "")} style={r.passed ? undefined : { color: "var(--muted)" }}>
                    {r.passed ? "GRADUATED" : "not yet"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
