"""Tunable parameters for the paper-trading bake-off. Edit freely."""
import os

# Universe: high-beta single stocks + leveraged ETFs (a mix, per "test all").
# Max 10 symbols fits one get_equity_historicals call.
UNIVERSE = [
    # Mega / large-cap tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "AVGO", "ORCL", "NFLX",
    # Semis
    "AMD", "INTC", "MU", "QCOM", "TXN", "MRVL", "SMCI", "ARM", "ASML", "TSM",
    # Software / high-growth
    "CRM", "ADBE", "PLTR", "SNOW", "CRWD", "NET", "DDOG", "SHOP", "UBER", "ABNB", "RBLX", "U",
    # Crypto-linked / fintech
    "COIN", "MSTR", "MARA", "RIOT", "HOOD", "SOFI",
    # EV / auto
    "RIVN", "LCID", "NIO", "F",
    # Energy
    "XOM", "CVX", "OXY", "SLB", "COP", "FANG", "DVN",
    # Financials
    "JPM", "BAC", "GS", "MS", "V", "MA", "PYPL", "AXP",
    # Healthcare / biotech
    "LLY", "UNH", "PFE", "MRNA", "AMGN", "ISRG", "VRTX", "REGN", "GILD",
    # Consumer / retail
    "COST", "WMT", "HD", "NKE", "SBUX", "MCD", "DIS", "CMG", "TGT",
    # Industrials / aero / defense
    "BA", "CAT", "GE", "LMT", "DE", "UPS",
    # Materials / gold / China
    "NEM", "FCX", "GOLD", "BABA", "PDD", "JD",
    # Leveraged / inverse / sector ETFs (both directions, for high variance + defense)
    "TQQQ", "SQQQ", "SOXL", "SOXS", "SPXL", "TNA", "FAS", "ERX", "LABU", "NUGT", "BOIL", "UVXY", "GLD",
]

# Benchmarks: fetched into the snapshot alongside the universe (so they stay fresh through the
# normal data pipeline) but NEVER traded — they only draw a reference line on the equity chart.
BENCHMARK_SYMBOL = "SPY"                  # S&P 500 proxy on the equity-curves chart
BENCHMARKS = {BENCHMARK_SYMBOL}
FETCH_SYMBOLS = UNIVERSE + [BENCHMARK_SYMBOL]  # the full pull list for a data refresh

STARTING_CASH = 100.0

# --- Risk controls (the "not gambling" part) ---
MAX_POSITIONS = 5
POSITION_SIZE_PCT = 1.0 / MAX_POSITIONS  # target fraction of equity per new position
STOP_LOSS_PCT = 0.15                      # hard per-position stop
CIRCUIT_BREAKER_EQUITY = 60.0             # halt NEW buys below this equity
SLIPPAGE_BPS = 5                          # simulated fill slippage each side (honest fills)

# --- Signal parameters ---
BREAKOUT_LOOKBACK = 20
VOL_LOOKBACK = 20
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
SMA_PERIOD = 20
WARMUP = 22                               # bars of history required before trading

# --- Agent paper accounts (analyst + swarm trade fake money before going live) ---
AGENT_NAMES = ["deep_research_analyst", "llm_voters", "mirofish_real", "congress_mirror"]
AGENT_MAX_WEIGHT = 0.6   # cap any single name in an agent's paper book (risk control)
MIROFISH_MAX_NAMES = 5   # MiroFish holds its top-N rank-weighted consensus names (was a hard 3-name cap)

# --- Congress-mirror competitor (follows the most successful politician investors) ---
# Data: kadoa-org/congress-trading-monitor, a free daily GitHub mirror of public STOCK Act
# disclosures (no API key, no Cloudflare). We rank by the mirror's own per-filer excess return,
# then mirror the top filers' disclosed PURCHASES — on the DISCLOSURE date, never backfilled to the
# (up-to-45-days-earlier) transaction date, which would be look-ahead. See tools/refresh_congress.py.
CONGRESS_MIN_SCORED_BUYS = 10   # follow every congress filer clearing this graded-buy floor (luck filter); no perf ranking
CONGRESS_LOOKBACK_DAYS = 120    # mirror a name while a followed filer's disclosure is this fresh
CONGRESS_MAX_NAMES = 6          # hold at most this many mirrored names

# Per-agent risk controls — harness-enforced, the agent never overrides these mid-trade.
#   stop_pct:       hard per-position stop fraction, or None to disable (e.g. a mean-reversion book).
#   breaker_equity: halt NEW buys below this equity, or None to disable.
# Missing agents/keys fall back to the globals above (STOP_LOSS_PCT / CIRCUIT_BREAKER_EQUITY); see
# paper.risk_for.
AGENT_RISK = {
    "deep_research_analyst": {"stop_pct": 0.20, "breaker_equity": CIRCUIT_BREAKER_EQUITY},  # deep-research: more room
    "llm_voters":        {"stop_pct": 0.15, "breaker_equity": CIRCUIT_BREAKER_EQUITY},  # short-horizon: cut faster
    "mirofish_real":         {"stop_pct": 0.15, "breaker_equity": CIRCUIT_BREAKER_EQUITY},  # social-sim swarm
    # ponytail: a 15% stop is a risk overlay on the raw mirror — it can exit a name a politician
    # still holds. Set stop_pct=None for a pure follow-the-disclosures book.
    "congress_mirror":       {"stop_pct": 0.15, "breaker_equity": CIRCUIT_BREAKER_EQUITY},  # politician mirror
}

# --- Go-live (NOT used during paper testing) ---
# Only the agentic-allowed cash account accepts agent orders (no options). Keep the real
# account number OUT of source control: set AGENTIC_ACCOUNT in .env (gitignored).
def _env(name, default=""):  # os.environ first, then .env (no dotenv dependency)
    v = os.environ.get(name)
    if v:
        return v.strip()
    env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


AGENTIC_ACCOUNT = _env("AGENTIC_ACCOUNT")
