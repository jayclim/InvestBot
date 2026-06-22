export const money = (v) => "$" + Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const pct = (v) => (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
export const cls = (v) => (v >= 0 ? "pos" : "neg");

export const RCOL = ["#2C44CE", "#C77F1A", "#7A3FC2", "#147A52", "#BE4527"];
export const MODELC = {
  "DeepSeek V3.2": "var(--m-deepseek)",
  "Gemini 2.5 Flash-Lite": "var(--m-gemini)",
  "Llama 4 Scout": "var(--m-llama)",
  "Haiku 4.5": "var(--m-haiku)",
};
