export const money = (v) => "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const pct = (v) => (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
export const cls = (v) => (v >= 0 ? "pos" : "neg");

export const RCOL = ["#2C44CE", "#C77F1A", "#7A3FC2", "#147A52", "#BE4527", "#0E8F9E"];
export const BENCH_COLOR = "#111827"; // S&P 500 benchmark — neutral graphite, drawn dashed (on the light chart/legend)
export const BENCH_INK = "#9CA3AF";   // ...and a light grey for the dark hover tooltip, where graphite is invisible

// A competitor/agent's colour = its slot in the standings order, so the equity-curve line,
// the legend, and the decision-trail rows all use one identity per method.
export const methodColor = (name, competitors) => {
  const i = (competitors || []).findIndex((c) => c.name === name);
  return RCOL[(i < 0 ? 0 : i) % RCOL.length];
};
export const MODELC = {
  "DeepSeek V3.2": "var(--m-deepseek)",
  "Gemini 2.5 Flash-Lite": "var(--m-gemini)",
  "Llama 4 Scout": "var(--m-llama)",
  "Haiku 4.5": "var(--m-haiku)",
};
