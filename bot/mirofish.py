"""Real-MiroFish-style swarm: persona agents with MEMORY that INTERACT over rounds.

Unlike bot/swarm.py (150 independent one-shot voters), here opinions propagate through a small
social graph and update across rounds — each agent re-votes seeing its own prior view and its
neighbours' latest views, so a consensus FORMS rather than being polled. That social-influence
dynamic is MiroFish's whole idea (and the reason it can herd). Seeded from the market briefing
plus an optional world-events news blob (state/news_seed.txt).

Costs more than the swarm: ~agents × rounds calls. Pick a TIER to bound cost; use estimate()
or `run_agents.py --estimate` before spending. Needs OPENROUTER_API_KEY (env or .env).

ponytail: skips MiroFish's GraphRAG/Neo4j "digital world" build — a knowledge graph of the seed
is overkill to pick from a ~100-name watchlist; the seed text in-prompt is enough. Add the graph
only if entity-level reasoning ever proves it earns the infra. Memory is one-step (own last view
+ neighbours' latest), not full history, to bound tokens — widen it if convergence needs it.
"""
import asyncio
import random

# Reuse the swarm's OpenRouter plumbing + persona generator (same package, internal reuse).
from bot import config as cfg
from bot.swarm import (BASE_SYSTEM, ENDPOINT, MAX_CONCURRENCY, TIMEOUT_S,
                       _api_key, _parse_ballot, build_briefing, fish_profiles)

# tier -> models (OpenRouter slugs) × how many agents × how many interaction rounds.
TIERS = {
    "cheap":   {"models": ["openai/gpt-4o-mini", "google/gemini-2.0-flash-001"], "agents": 30, "rounds": 6},
    "default": {"models": ["openai/gpt-4o-mini", "google/gemini-2.0-flash-001"], "agents": 44, "rounds": 10},
    "qwen":    {"models": ["qwen/qwen-plus"],                                     "agents": 44, "rounds": 10},
}

# Approx OpenRouter $/1M tokens (input, output) — for the estimate() guard only, NOT billing.
PRICES = {
    "openai/gpt-4o-mini":          (0.15, 0.60),
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "qwen/qwen-plus":              (0.40, 1.20),
}


def estimate(tier):
    """Rough cost/volume for a run, before spending. avg-tokens are deliberate guesses; later
    rounds carry more (own view + peers), so a wide low/high band brackets memory growth."""
    t = TIERS[tier]
    calls = t["agents"] * t["rounds"]
    in_tok, out_tok = 2500, 120                       # avg per call (briefing + persona + peers)
    pin = sum(PRICES[m][0] for m in t["models"]) / len(t["models"])
    pout = sum(PRICES[m][1] for m in t["models"]) / len(t["models"])
    mid = calls * (in_tok * pin + out_tok * pout) / 1e6
    return {"tier": tier, "agents": t["agents"], "rounds": t["rounds"], "calls": calls,
            "cost_low": round(mid * 0.7, 2), "cost_mid": round(mid, 2), "cost_high": round(mid * 2.5, 2)}


def _neighbors(n, k=4, seed=11):
    """Each agent's social graph: k random peers, no self-loops."""
    rng = random.Random(seed)
    return [rng.sample([j for j in range(n) if j != i], min(k, n - 1)) for i in range(n)]


def _system(prof):
    return (BASE_SYSTEM + f"\n\nYour lens ({prof['persona']}): {prof['lens']} "
            f"You are {prof['risk']}. Your horizon is {prof['horizon']}. {prof['quirk']}")


def _round_user(briefing, prev, neighbor_views):
    """Round 0 = just the briefing. Later rounds add the agent's own last view + peers' latest
    (the memory + social-influence step)."""
    if prev is None:
        return briefing
    peers = "\n".join(f" - {v['vote']}: {v['thesis']}" for v in neighbor_views) or " - (no peer signal)"
    return (briefing + f"\n\nYour current view: {prev['vote']} — {prev['thesis']}"
            f"\nYour panel neighbours now say:\n{peers}"
            "\nReconsider with your peers in mind, then commit to your single best pick — keep it "
            "or change it, through your own lens.")


async def _ask(client, sem, key, slug, system, user, universe):
    payload = {"model": slug, "max_tokens": 150, "temperature": 1.0,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with sem:
        for attempt in range(2):
            try:
                r = await client.post(ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT_S)
                r.raise_for_status()
                b = _parse_ballot(r.json()["choices"][0]["message"]["content"], universe)
                if b:
                    return b
            except Exception:
                if attempt == 0:
                    await asyncio.sleep(1.0)
        return None


def _tally(views):
    t = {}
    for v in views:
        if v:
            t[v["vote"]] = t.get(v["vote"], 0) + 1
    return t


async def _run(snapshot, universe, tier, seed_news):
    import httpx
    t = TIERS[tier]
    key = _api_key()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set (env or .env)")

    briefing = build_briefing(snapshot, universe)
    if seed_news:
        briefing = "World-events seed (recent headlines / signals):\n" + seed_news.strip() + "\n\n" + briefing

    n, rounds = t["agents"], t["rounds"]
    models = (t["models"] * (n // len(t["models"]) + 1))[:n]
    random.Random(7).shuffle(models)
    profiles = fish_profiles(n)
    systems = [_system(p) for p in profiles]
    neighbors = _neighbors(n)

    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    views = [None] * n              # latest ballot per agent (None until it first answers)
    convergence = []
    async with httpx.AsyncClient() as client:
        for r in range(rounds):
            users = [_round_user(briefing, views[i], [views[j] for j in neighbors[i] if views[j]])
                     for i in range(n)]
            res = await asyncio.gather(*[_ask(client, sem, key, models[i], systems[i], users[i], universe)
                                         for i in range(n)])
            for i, b in enumerate(res):
                if b:
                    views[i] = b   # keep prior view if a call failed this round
            tally = _tally(views)
            voted = sum(tally.values())
            top = max(tally.items(), key=lambda kv: kv[1]) if tally else ("CASH", 0)
            convergence.append({"round": r + 1, "top": top[0], "share": round(top[1] / max(1, voted), 3)})

    final = [v for v in views if v]
    if not final:
        raise RuntimeError("every agent failed — check OpenRouter key / model slugs")
    tally = _tally(final)
    ballots = sorted(([s, c] for s, c in tally.items()), key=lambda x: x[1], reverse=True)
    return {
        "date": sorted({b.date for bars in snapshot.values() for b in bars})[-1],
        "call": ballots[0][0], "action": "buy" if ballots[0][0] != "CASH" else "hold",
        "confidence": round(ballots[0][1] / len(final), 3),
        "total_fish": len(final), "ballots": ballots, "tier": tier, "rounds": rounds,
        "models": sorted(set(t["models"])), "convergence": convergence, "seeded_news": bool(seed_news),
        "note": f"Real-MiroFish swarm — {len(final)} persona agents with memory interacted over "
                f"{rounds} rounds (tier '{tier}'); consensus formed via peer influence.",
        "live": True,
    }


def run_mirofish(snapshot, universe, tier="cheap", seed_news=None):
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier!r}; pick one of {list(TIERS)}")
    return asyncio.run(_run(snapshot, universe, tier, seed_news))


if __name__ == "__main__":  # ponytail: offline self-check — no network, no spend
    import json
    for name in TIERS:
        e = estimate(name)
        assert e["calls"] == TIERS[name]["agents"] * TIERS[name]["rounds"]
        assert 0 < e["cost_low"] <= e["cost_mid"] <= e["cost_high"]
    nb = _neighbors(30)
    assert len(nb) == 30 and all(i not in nb[i] for i in range(30))      # no self-loops
    assert _round_user("BRIEF", None, []) == "BRIEF"                     # round 0 = briefing only
    u = _round_user("BRIEF", {"vote": "NVDA", "thesis": "x"}, [{"vote": "MU", "thesis": "y"}])
    assert "NVDA" in u and "MU" in u                                     # later round shows self + peer
    print(json.dumps({t: estimate(t) for t in TIERS}, indent=1))
    print("ok")
