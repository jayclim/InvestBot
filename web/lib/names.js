// Ticker → company / fund name for the fixed universe (bot/config.py). Static so the UI needs
// no runtime lookup; unknown tickers fall back to the bare symbol.
export const NAMES = {
  AAPL: "Apple", MSFT: "Microsoft", GOOGL: "Alphabet", AMZN: "Amazon",
  META: "Meta Platforms", NVDA: "NVIDIA", TSLA: "Tesla", AVGO: "Broadcom",
  ORCL: "Oracle", NFLX: "Netflix", AMD: "Advanced Micro Devices", INTC: "Intel",
  MU: "Micron Technology", QCOM: "Qualcomm", TXN: "Texas Instruments",
  MRVL: "Marvell Technology", SMCI: "Super Micro Computer", ARM: "Arm Holdings",
  ASML: "ASML Holding", TSM: "Taiwan Semiconductor", CRM: "Salesforce", ADBE: "Adobe",
  PLTR: "Palantir Technologies", SNOW: "Snowflake", CRWD: "CrowdStrike", NET: "Cloudflare",
  DDOG: "Datadog", SHOP: "Shopify", UBER: "Uber Technologies", ABNB: "Airbnb",
  RBLX: "Roblox", U: "Unity Software", COIN: "Coinbase", MSTR: "Strategy (MicroStrategy)",
  MARA: "MARA Holdings", RIOT: "Riot Platforms", HOOD: "Robinhood Markets",
  SOFI: "SoFi Technologies", RIVN: "Rivian Automotive", LCID: "Lucid Group", NIO: "NIO",
  F: "Ford Motor", XOM: "Exxon Mobil", CVX: "Chevron", OXY: "Occidental Petroleum",
  SLB: "SLB (Schlumberger)", COP: "ConocoPhillips", FANG: "Diamondback Energy",
  DVN: "Devon Energy", JPM: "JPMorgan Chase", BAC: "Bank of America", GS: "Goldman Sachs",
  MS: "Morgan Stanley", V: "Visa", MA: "Mastercard", PYPL: "PayPal",
  AXP: "American Express", LLY: "Eli Lilly", UNH: "UnitedHealth Group", PFE: "Pfizer",
  MRNA: "Moderna", AMGN: "Amgen", ISRG: "Intuitive Surgical", VRTX: "Vertex Pharmaceuticals",
  REGN: "Regeneron Pharmaceuticals", GILD: "Gilead Sciences", COST: "Costco Wholesale",
  WMT: "Walmart", HD: "Home Depot", NKE: "Nike", SBUX: "Starbucks", MCD: "McDonald's",
  DIS: "Walt Disney", CMG: "Chipotle Mexican Grill", TGT: "Target", BA: "Boeing",
  CAT: "Caterpillar", GE: "GE Aerospace", LMT: "Lockheed Martin", DE: "Deere & Co.",
  UPS: "United Parcel Service", NEM: "Newmont", FCX: "Freeport-McMoRan",
  GOLD: "Barrick Gold", BABA: "Alibaba", PDD: "PDD Holdings", JD: "JD.com",
  TQQQ: "ProShares UltraPro QQQ", SQQQ: "ProShares UltraPro Short QQQ",
  SOXL: "Direxion Daily Semiconductor Bull 3X", SOXS: "Direxion Daily Semiconductor Bear 3X",
  SPXL: "Direxion Daily S&P 500 Bull 3X", TNA: "Direxion Daily Small Cap Bull 3X",
  FAS: "Direxion Daily Financial Bull 3X", ERX: "Direxion Daily Energy Bull 2X",
  LABU: "Direxion Daily S&P Biotech Bull 3X", NUGT: "Direxion Daily Gold Miners Bull 2X",
  BOIL: "ProShares Ultra Bloomberg Natural Gas", UVXY: "ProShares Ultra VIX Short-Term Futures",
  GLD: "SPDR Gold Shares",
};

// "Apple (AAPL)" — or just the ticker if we don't have a name for it.
export const named = (s) => (NAMES[s] ? `${NAMES[s]} (${s})` : s);
