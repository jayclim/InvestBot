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
import datetime as _dt
import itertools
import json
import os
import random
import re

from bot import config as cfg
from bot.indicators import sma

# (openrouter_slug, display_name, how_many_fish). Heterogeneous on purpose.
FISH_MODELS = [
    ("deepseek/deepseek-chat",          "DeepSeek V3.2",          50),
    ("google/gemini-2.5-flash-lite",    "Gemini 2.5 Flash-Lite",  50),
    ("qwen/qwen-plus",                  "Qwen Plus",              20),
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

# Each fish sees a different random slice of the universe (not the whole list) so the panel
# can't all pile into the same hot name — that herding is what an independent vote should avoid.
VOTER_SLICE = 20
NEWS_URL = "https://finnhub.io/api/v1/company-news"
NEWS_RATE_PER_MIN = 55  # stay under Finnhub's free 60/min when sweeping the whole universe

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


def _env_key(name):
    key = os.environ.get(name)
    if key:
        return key.strip()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.path.join(root, ".env")
    if os.path.exists(env):
        for line in open(env):
            if line.strip().startswith(name):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _api_key():
    return _env_key("OPENROUTER_API_KEY")


def build_briefing(snapshot, symbols, headlines=None, rng=random):
    """Briefing over just `symbols` (a per-fish random slice, in the order given). When
    `headlines` is provided, each name gets ONE randomly-picked recent headline so different
    fish reason about different news on the same stock."""
    lines = ["Watchlist snapshot (recent daily bars). Columns: last, 5d%, 20d%, vs-20d-SMA."
             " Some names carry a recent headline."]
    for sym in symbols:
        bars = snapshot.get(sym)
        if not bars or len(bars) < 21:
            continue
        closes = [b.close for b in bars]
        last = closes[-1]
        r5 = last / closes[-6] - 1
        r20 = last / closes[-21] - 1
        s20 = sma(closes, 20)
        vs = (last / s20 - 1) if s20 else 0.0
        line = f"{sym:6s} {last:9.2f}  {r5*100:+6.1f}%  {r20*100:+7.1f}%  {vs*100:+6.1f}%"
        hs = (headlines or {}).get(sym)
        if hs:
            h = rng.choice(hs)
            line += f'  · "{h["h"]}" ({h["src"]})' if h["src"] else f'  · "{h["h"]}"'
        lines.append(line)
    lines.append("\nPick ONE name from THIS list (or CASH) through your own lens. You are one vote among many.")
    return "\n".join(lines)


def _news_path(path):
    return path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "news.json")


async def _fetch_one_news(client, sym, fkey, frm, to):
    try:
        r = await client.get(NEWS_URL, params={"symbol": sym, "from": frm, "to": to, "token": fkey}, timeout=8)
        if r.status_code != 200:
            return []
        j = r.json()
    except Exception:
        return []
    if not isinstance(j, list):
        return []
    items = sorted((n for n in j if isinstance(n, dict) and n.get("headline")),
                   key=lambda n: n.get("datetime", 0), reverse=True)
    return [{"headline": n["headline"][:140], "url": n.get("url", ""),
             "source": (n.get("source") or "")[:24], "datetime": n.get("datetime", 0)} for n in items[:6]]


async def _fetch_universe_news(universe, fkey):
    """Sequential + paced under Finnhub's free 60/min so we get EVERY name. ~2 min for the whole
    universe — but it runs once per calendar day (cache-by-date), then reads are instant."""
    import httpx
    to = _dt.date.today().isoformat()
    frm = (_dt.date.today() - _dt.timedelta(days=30)).isoformat()
    gap = 60.0 / NEWS_RATE_PER_MIN
    out = {}
    async with httpx.AsyncClient() as client:
        for sym in universe:
            out[sym] = await _fetch_one_news(client, sym, fkey, frm, to)
            await asyncio.sleep(gap)  # ponytail: rate ceiling; drop the sleep on a paid Finnhub tier
    return {s: v for s, v in out.items() if v}


def refresh_news(universe, path=None, today=None):
    """Fetch every name's recent headlines ONCE per calendar day, cache to `path`
    ({date, asof, items:{sym:[{headline,url,source,datetime}]}}), reuse the cache the rest of the
    day. No FINNHUB_API_KEY or upstream error -> keep whatever's cached (headlines are enrichment)."""
    path = _news_path(path)
    today = today or _dt.date.today().isoformat()
    try:
        cache = json.load(open(path))
    except Exception:
        cache = {}
    if cache.get("date") == today and cache.get("items"):
        return cache
    fkey = _env_key("FINNHUB_API_KEY")
    if not fkey:
        return cache or {"date": today, "items": {}}
    items = asyncio.run(_fetch_universe_news(universe, fkey))
    out = {"date": today, "asof": _dt.datetime.now().isoformat(timespec="seconds"), "items": items}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(out, open(path, "w"))
    return out


def load_news(path=None):
    """Cached headlines in the swarm's briefing shape: {sym: [{h, src}, …]}."""
    try:
        items = json.load(open(_news_path(path))).get("items", {})
    except Exception:
        return {}
    return {s: [{"h": n["headline"][:100], "src": n.get("source", "")} for n in arr]
            for s, arr in items.items() if arr}


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


async def _run(snapshot, universe, headlines):
    import httpx
    key = _api_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set (env or .env)")
    eligible = [s for s in universe if snapshot.get(s) and len(snapshot[s]) >= 21]
    if not eligible:
        raise RuntimeError("no symbols with >=21 bars to build a briefing")

    # 150 fish: each a (model) paired with a UNIQUE profile.
    models = []
    for slug, name, n in FISH_MODELS:
        models += [(slug, name)] * n
    random.Random(7).shuffle(models)
    profiles = fish_profiles(len(models))

    rng = random.Random()  # fresh each run -> different slices every run
    k = min(VOTER_SLICE, len(eligible))
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    tasks = []
    async with httpx.AsyncClient() as client:
        for fid, ((slug, name), prof) in enumerate(zip(models, profiles), 1):
            shown = rng.sample(eligible, k)  # random sample IS the shuffle (random order)
            briefing = build_briefing(snapshot, shown, headlines, rng)
            tasks.append(_one_fish(client, sem, key, slug, name, fid, prof, briefing, shown))
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
        "note": f"Live swarm — {len(fish)} fish, each a unique trader profile shown its own random "
                f"~{VOTER_SLICE}-name slice of the watchlist (with recent headlines), voted via OpenRouter. "
                "Independent-voter election; dissenters (ringed) chose CASH.",
        "live": True,
    }


def run_swarm(snapshot, universe, headlines=None):
    return asyncio.run(_run(snapshot, universe, headlines or {}))


if __name__ == "__main__":  # self-check: slicing + headline injection, no network
    import types
    _bars = [types.SimpleNamespace(close=100 + i, date=f"d{i}") for i in range(25)]
    _snap = {f"S{i}": _bars for i in range(50)}
    _heads = {"S1": [{"h": "S1 lands a huge contract", "src": "Reuters"}]}
    _rng = random.Random(1)
    _shown = _rng.sample(list(_snap), VOTER_SLICE)
    assert len(_shown) == VOTER_SLICE, "slice must be exactly VOTER_SLICE names"
    _b = build_briefing(_snap, _shown, _heads, _rng)
    _data = {l.split()[0] for l in _b.splitlines() if l[:1] == "S"}  # data lines start with the symbol
    assert _data == set(_shown), "exactly the shown names appear — nothing outside the slice leaks in"
    assert "huge contract" in build_briefing(_snap, ["S1"], _heads, _rng), "headline shows for its symbol"
    assert "huge contract" not in build_briefing(_snap, ["S3"], _heads, _rng), "no headline for a name without news"
    print("swarm self-check ok")
