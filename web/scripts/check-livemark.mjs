// Self-check for the queued-order fill simulation (components/LiveQuotes.jsx).
// Run: node scripts/check-livemark.mjs
// The functions under test are plain JS at the tail of the JSX file — evaluate that slice as-is.
import { readFileSync } from "node:fs";
import assert from "node:assert";

const src = readFileSync(new URL("../components/LiveQuotes.jsx", import.meta.url), "utf8");
const tail = src.slice(src.indexOf("// ET wall-clock")).replaceAll("export function", "function");
const { simFillPrice, liveMark } = new Function(tail + "\nreturn { simFillPrice, liveMark };")();

const T_RTH = Date.UTC(2026, 5, 30, 14, 0) / 1000; // 2026-06-30 10:00 ET (EDT)
const T_PRE = Date.UTC(2026, 5, 30, 12, 0) / 1000; // 2026-06-30 08:00 ET — before the open
const q = { price: 11, open: 10, high: 11.5, low: 9.5, t: T_RTH };

// MOO fills at the session open once a session AFTER placed_session has opened
assert.equal(simFillPrice({ side: "buy", kind: "moo", placed_session: "2026-06-29" }, q), 10);
// same session as placement, or pre-open → not filled yet
assert.equal(simFillPrice({ side: "buy", kind: "moo", placed_session: "2026-06-30" }, q), null);
assert.equal(simFillPrice({ side: "buy", kind: "moo", placed_session: "2026-06-29" }, { ...q, t: T_PRE }), null);
// limit buy: needs the session low to trade through; fills at min(open, limit)
assert.equal(simFillPrice({ side: "buy", kind: "limit", limit: 9.0, placed_session: "2026-06-29" }, q), null);
assert.equal(simFillPrice({ side: "buy", kind: "limit", limit: 9.8, placed_session: "2026-06-29" }, q), 9.8);
// limit sell: needs the session high; fills at max(open, limit)
assert.equal(simFillPrice({ side: "sell", kind: "limit", limit: 11.2, qty: 1, placed_session: "2026-06-29" }, q), 11.2);
// stale seed quotes (no open/t) never simulate a fill
assert.equal(simFillPrice({ side: "buy", kind: "moo", placed_session: "2026-06-29" }, { price: 11, stale: true }), null);

// liveMark: a $50 MOO buy queued yesterday fills at the open (10) → 5 sh worth 11 now
let c = { cash: 100, holdings: [], open_orders: [{ symbol: "X", side: "buy", kind: "moo", dollars: 50, placed_session: "2026-06-29" }] };
let mk = liveMark(c, { X: q }, 100);
assert.ok(Math.abs(mk.equity - 105) < 1e-9, `buy sim equity ${mk.equity}`);
assert.ok(mk.fills.has(0));

// queued sell converts shares to cash at the open
c = { cash: 0, holdings: [{ symbol: "X", qty: 2, avg_price: 8, last: 10 }],
      open_orders: [{ symbol: "X", side: "sell", kind: "moo", qty: 2, placed_session: "2026-06-29" }] };
mk = liveMark(c, { X: q }, 100);
assert.ok(Math.abs(mk.equity - 20) < 1e-9, `sell sim equity ${mk.equity}`);

// no live feed → reproduces the published book exactly, nothing simulated
mk = liveMark(c, {}, 100);
assert.ok(Math.abs(mk.equity - 20) < 1e-9 && mk.fills.size === 0 && !mk.priced);

console.log("check-livemark: all assertions passed");
