"use client";
import { MODELC } from "../lib/format";
import { useModal, InfoButton } from "./ModalContext";

export default function Swarm({ data }) {
  const s = data.swarm;
  const { open } = useModal();
  if (!s) return null;

  const np = new Set(s.fish.map((f) => f.persona).filter(Boolean)).size;
  const byVote = {};
  s.fish.forEach((f) => (byVote[f.vote] = byVote[f.vote] || []).push(f));

  function fishModal(f) {
    open(
      <>
        <div className="modal-eyebrow">Fish #{f.id} · {f.model} · {f.persona || ""}</div>
        <h3>Voted {f.vote}{f.dissent ? " (dissent)" : ""}</h3>
        <p>{f.thesis}</p>
        {f.profile && <p className="note"><b>Profile:</b> {f.profile}</p>}
        <p className="note">One independent ballot — this fish read the same shared briefing as the others and committed to a single pick; it never saw any other fish&apos;s answer.{s.is_mock ? " (Mock data.)" : ""}</p>
      </>
    );
  }

  return (
    <section>
      <div className="eyebrow">
        <span className="n">03</span>
        <h2>Swarm vote</h2>
        <InfoButton title="Swarm vote">
          An independent-voter election: 150 unique-profile cheap models each read one shared briefing and return a single ballot (top pick or CASH) via OpenRouter, then we tally. No fish sees another&apos;s answer. Confidence = the winning pick&apos;s share of all ballots.
        </InfoButton>
        <span className="hint">{s.total_fish} fish · {np ? np + " personas · " : ""}{s.models.map((m) => m.n + " " + m.name.split(" ")[0]).join(" · ")}</span>
      </div>
      <p className="cap">Independent-voter election over the watchlist. Each dot is one fish, colored by model. <b>Click a dot</b> for that fish&apos;s ballot; ringed dots are dissenters.</p>
      <div className="card pad">
        <div className="callhero">
          <span className="big">Swarm call: <span className={s.action === "buy" ? "buy" : ""}>{s.call}</span></span>
          <span className="mono" style={{ color: "var(--muted)" }}>{(s.confidence * 100).toFixed(0)}% of ballots · {s.action.toUpperCase()}</span>
          <span className={"badge " + (s.is_mock ? "mock" : "live")} style={{ marginLeft: "auto" }}>{s.is_mock ? "mock · not yet wired" : "live"}</span>
        </div>
        <div className="fishcols">
          {s.ballots.map(([sym, n]) => (
            <div key={sym} className={"fcol" + (sym === s.call ? " win" : "") + (sym === "CASH" ? " cash" : "")}>
              <div className="stack">
                {(byVote[sym] || []).map((f) => (
                  <i
                    key={f.id}
                    className={"fish" + (f.dissent ? " diss" : "")}
                    style={{ background: MODELC[f.model] || "#999" }}
                    title={`${f.model} · ${f.persona || ""}`}
                    onClick={() => fishModal(f)}
                  />
                ))}
              </div>
              <div className="lab">{sym}</div>
              <div className="cnt">{n}</div>
            </div>
          ))}
        </div>
        <div className="modlegend">
          {s.models.map((m) => (
            <span key={m.name}><i className="mdot" style={{ background: MODELC[m.name] || "#999" }} />{m.name} <b className="mono">{m.n}</b></span>
          ))}
          <span><i className="mdot" style={{ background: "transparent", boxShadow: "0 0 0 1.5px var(--ink)" }} />dissenter</span>
        </div>
        <p className="note">{s.note || ""}</p>
        <details>
          <summary>All ballots (every fish&apos;s vote &amp; one-line thesis)</summary>
          <div className="fl">
            {s.fish.map((f) => (
              <div key={f.id} className={"fi" + (f.dissent ? " diss" : "")} onClick={() => fishModal(f)}>
                <i className="mi" style={{ background: MODELC[f.model] || "#999" }} />
                <span className="vt">{f.vote}</span>
                <span className="th"><b className="pz">{f.persona || ""}</b>{f.thesis}</span>
              </div>
            ))}
          </div>
        </details>
      </div>
    </section>
  );
}
