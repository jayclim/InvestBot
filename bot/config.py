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

STARTING_CASH = 100.0

# --- Risk controls (the "not gambling" part) ---
MAX_POSITIONS = 3
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
AGENT_NAMES = ["deep_research_analyst", "llm_voters", "mirofish_real"]
AGENT_MAX_WEIGHT = 0.6   # cap any single name in an agent's paper book (risk control)

# Per-agent risk controls — harness-enforced, the agent never overrides these mid-trade.
#   stop_pct:       hard per-position stop fraction, or None to disable (e.g. a mean-reversion book).
#   breaker_equity: halt NEW buys below this equity, or None to disable.
# Missing agents/keys fall back to the globals above (STOP_LOSS_PCT / CIRCUIT_BREAKER_EQUITY); see
# paper.risk_for.
AGENT_RISK = {
    "deep_research_analyst": {"stop_pct": 0.20, "breaker_equity": CIRCUIT_BREAKER_EQUITY},  # deep-research: more room
    "llm_voters":        {"stop_pct": 0.15, "breaker_equity": CIRCUIT_BREAKER_EQUITY},  # short-horizon: cut faster
    "mirofish_real":         {"stop_pct": 0.15, "breaker_equity": CIRCUIT_BREAKER_EQUITY},  # social-sim swarm
}

# --- Go-live (NOT used during paper testing) ---
# Only the agentic-allowed cash account accepts agent orders (no options). Keep the real
# account number OUT of source control: set AGENTIC_ACCOUNT in .env (gitignored).
AGENTIC_ACCOUNT = os.environ.get("AGENTIC_ACCOUNT", "")
