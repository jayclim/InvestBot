"""The mirofish swarm — independent-voter election over the watchlist via OpenRouter.

Each "fish" is a cheap model with a UNIQUE trader profile: a base persona (lens) plus a
risk appetite, a time horizon, and a personal quirk. All 150 fish differ from one another.
Each reads ONE shared market briefing and returns a single ballot (top pick or CASH) with a
one-line thesis; we tally the ballots. Fish never see each other — independence is what makes
the majority signal work, and the unique profiles keep them from voting as clones.

Borrows MiroFish's idea of many distinct persona-agents, without its heavy multi-round
social-simulation (which herds). Needs an OpenRouter key:
    export OPENROUTER_API_KEY=sk-or-...    (or put it in .env)
"""
import asyncio
import itertools
import json
import os
import random
import re

from bot import config as cfg
from bot.indicators import sma

# (openrouter_slug, display_name, how_many_fish). Heterogeneous on purpose.
FISH_MODELS = [
    ("deepseek/deepseek-chat",          "DeepSeek V3.2",          60),
    ("google/gemini-2.5-flash-lite",    "Gemini 2.5 Flash-Lite",  60),
    ("meta-llama/llama-4-scout",        "Llama 4 Scout",          20),
    ("anthropic/claude-haiku-4.5",      "Haiku 4.5",              10),
]

# A fish's character = persona × risk × horizon × quirk (1,080 combinations; we draw a
# unique one per fish, so all 150 differ).
PERSONAS = [
    ("momentum",     "You chase strength — names with the strongest recent momentum that look likely to keep running."),
    ("contrarian",   "You fade extremes — distrust what just ran, prefer beaten-down names set to mean-revert."),
    ("value",        "You want the cheapest decent risk/reward — laggards and reasonable entries, not crowded winners."),
    ("macro",        "You think top-down for a late-cycle, possibly-hawkish-Fed regime — energy, financials, or gold over long-duration tech."),
    ("risk_manager", "You prioritize not blowing up — avoid the most extended/volatile names."),
    ("narrative",    "You follow the story and the crowd — the name with the strongest sentiment right now."),
    ("technician",   "You read the chart — clean breakouts and constructive setups, not broken ones."),
    ("rotator",      "You bet on what leads next, not what led last — rotate toward the sleeve about to outperform."),
    ("event_driven", "You hunt catalysts — names with an upcoming event that could move them sharply."),
    ("skeptic",      "You look for what's most overextended and likely to fall — favor defensive/inverse exposure."),
]
RISK = ["cautious (capital preservation first)", "balanced", "aggressive (swinging for big gains)"]
HORIZON = ["the next few days", "the next couple of weeks", "the next month or more"]
QUIRKS = [
    "You distrust leveraged ETFs and avoid them unless the edge is overwhelming.",
    "You love a clean catalyst and will pay up for an upcoming event.",
    "You hate crowded trades and avoid whatever everyone is talking about.",
    "You anchor on the 52-week range and like fresh breakouts.",
    "You weigh volume heavily — no thesis without participation.",
    "You favor relative strength versus the sector over absolute moves.",
    "You keep dry powder and pick CASH more readily than most.",
    "You hunt oversold bounces in otherwise-strong names.",
    "You prefer liquid mega-caps over small, jumpy names.",
    "You like asymmetric lottery tickets even if most go to zero.",
    "You rotate toward whatever sleeve has lagged and looks ready to turn.",
    "You cut anything that smells like a falling knife.",
]

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
MAX_CONCURRENCY = 24
TIMEOUT_S = 40

BASE_SYSTEM = (
    "You are one trader in a large independent panel. You get a briefing on a watchlist and "
    "must commit to a single highest-conviction idea for a high-variance, short-horizon paper "
    "account. Reply with ONLY a JSON object: "
    '{\"pick\": \"<TICKER or CASH>\", \"thesis\": \"<one sentence, <=140 chars>\"}. '
    "Pick CASH if nothing fits your style with good risk/reward."
)


def fish_profiles(n_total, seed=17):
    """Return n_total UNIQUE trader profiles (persona × risk × horizon × quirk)."""
    combos = list(itertools.product(PERSONAS, RISK, HORIZON, QUIRKS))
    random.Random(seed).shuffle(combos)
    out = []
    for (pname, plens), risk, horizon, quirk in combos[:n_total]:
        out.append({
            "persona": pname, "lens": plens, "risk": risk, "horizon": horizon, "quirk": quirk,
            "desc": f"{risk.split(' (')[0]} · {horizon} · {quirk}",
        })
    return out


def _api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key.strip()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.path.join(root, ".env")
    if os.path.exists(env):
        for line in open(env):
            if line.strip().startswith("OPENROUTER_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def build_briefing(snapshot, universe):
    lines = ["Watchlist snapshot (recent daily bars). Columns: last, 5d%, 20d%, vs-20d-SMA."]
    for sym in universe:
        bars = snapshot.get(sym)
        if not bars or len(bars) < 21:
            continue
        closes = [b.close for b in bars]
        last = closes[-1]
        r5 = last / closes[-6] - 1
        r20 = last / closes[-21] - 1
        s20 = sma(closes, 20)
        vs = (last / s20 - 1) if s20 else 0.0
        lines.append(f"{sym:6s} {last:9.2f}  {r5*100:+6.1f}%  {r20*100:+7.1f}%  {vs*100:+6.1f}%")
    lines.append("\nPick ONE name (or CASH) through your own lens. You are one vote among many.")
    return "\n".join(lines)


def _parse_ballot(text, universe):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except Exception:
        return None
    pick = str(obj.get("pick", "")).upper().strip()
    if pick not in universe and pick != "CASH":
        return None
    thesis = str(obj.get("thesis", "")).strip()[:160]
    return {"vote": pick, "thesis": thesis or "(no rationale given)"}


async def _one_fish(client, sem, key, slug, model_name, fid, prof, briefing, universe):
    system = (BASE_SYSTEM + f"\n\nYour lens ({prof['persona']}): {prof['lens']} "
              f"You are {prof['risk']}. Your horizon is {prof['horizon']}. {prof['quirk']}")
    async with sem:
        payload = {"model": slug, "messages": [{"role": "system", "content": system},
                   {"role": "user", "content": briefing}], "max_tokens": 120, "temperature": 1.0}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        for attempt in range(2):
            try:
                r = await client.post(ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT_S)
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
                ballot = _parse_ballot(text, universe)
                if ballot:
                    ballot.update({"id": fid, "model": model_name, "persona": prof["persona"],
                                   "profile": prof["desc"], "dissent": ballot["vote"] == "CASH"})
                    return ballot
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(1.0)
        return None


async def _run(snapshot, universe):
    import httpx
    key = _api_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set (env or .env)")
    briefing = build_briefing(snapshot, universe)

    # 150 fish: each a (model) paired with a UNIQUE profile.
    models = []
    for slug, name, n in FISH_MODELS:
        models += [(slug, name)] * n
    random.Random(7).shuffle(models)
    profiles = fish_profiles(len(models))

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    tasks = []
    async with httpx.AsyncClient() as client:
        for fid, ((slug, name), prof) in enumerate(zip(models, profiles), 1):
            tasks.append(_one_fish(client, sem, key, slug, name, fid, prof, briefing, universe))
        results = await asyncio.gather(*tasks)
    fish = [f for f in results if f]
    if not fish:
        raise RuntimeError("every fish failed — check OpenRouter key / model slugs")

    tally = {}
    for f in fish:
        tally[f["vote"]] = tally.get(f["vote"], 0) + 1
    ballots = sorted(([s, n] for s, n in tally.items()), key=lambda x: x[1], reverse=True)
    top = ballots[0][0]
    models_out = [{"name": name, "n": sum(1 for f in fish if f["model"] == name)}
                  for _, name, _ in FISH_MODELS]
    return {
        "date": sorted({b.date for bars in snapshot.values() for b in bars})[-1],
        "call": top, "action": "buy" if top != "CASH" else "hold",
        "confidence": round(ballots[0][1] / len(fish), 3),
        "total_fish": len(fish), "ballots": ballots, "models": models_out, "fish": fish,
        "note": f"Live swarm — {len(fish)} fish, each a unique trader profile, voted via OpenRouter. "
                "Independent-voter election; dissenters (ringed) chose CASH.",
        "live": True,
    }


def run_swarm(snapshot, universe):
    return asyncio.run(_run(snapshot, universe))
