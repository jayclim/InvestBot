export const money = (v) => "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const pct = (v) => (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
export const cls = (v) => (v >= 0 ? "pos" : "neg");

export const RCOL = ["#2C44CE", "#C77F1A", "#7A3FC2", "#147A52", "#BE4527", "#0E8F9E"];
export const BENCH_COLOR = "#6B7280"; // S&P 500 benchmark — neutral mid-grey, drawn dashed; lighter than --ink so it doesn't blend into the zero-axis/labels
export const BENCH_INK = "#9CA3AF";   // ...and a lighter grey for the dark hover tooltip, where mid-grey is faint

// A competitor/agent's colour = its slot in the standings order, so the equity-curve line,
// the legend, and the decision-trail rows all use one identity per method.
export const methodColor = (name, competitors) => {
  if (name === "S&P 500") return BENCH_COLOR; // the market baseline — graphite, drawn dashed
  // rank among the real competitors only, so S&P 500's slot never shifts the others' colours
  const others = (competitors || []).filter((c) => c.name !== "S&P 500");
  const i = others.findIndex((c) => c.name === name);
  return RCOL[(i < 0 ? 0 : i) % RCOL.length];
};
export const MODELC = {
  "DeepSeek V3.2": "var(--m-deepseek)",
  "Gemini 2.5 Flash-Lite": "var(--m-gemini)",
  "Llama 4 Scout": "var(--m-llama)",
  "Haiku 4.5": "var(--m-haiku)",
};
