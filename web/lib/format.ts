export function pct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "–";
  return (x * 100).toFixed(digits) + "%";
}

export function signedPct(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "–";
  const s = (x * 100).toFixed(digits);
  return (x > 0 ? "+" : "") + s + "%";
}

export function usd(x: number | null | undefined, digits = 0): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "–";
  return "$" + x.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function usdK(x: number | null | undefined): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "–";
  if (Math.abs(x) >= 1e6) return "$" + (x / 1e6).toFixed(2) + "M";
  return "$" + (x / 1e3).toFixed(1) + "k";
}

export function num(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || !Number.isFinite(x)) return "–";
  return x.toFixed(digits);
}

export function shortId(id: string | null | undefined): string {
  if (!id) return "–";
  return id.slice(0, 10);
}

export const ASSET_LABELS: Record<string, string> = {
  us_eq: "US equity",
  intl_eq: "Intl developed",
  em_eq: "Emerging mkts",
  reit: "REITs",
  gold: "Gold",
  tbill: "T-bills",
  ust_2y: "Treasury 2Y",
  ust_5y: "Treasury 5Y",
  ust_10y: "Treasury 10Y",
  ust_20y: "Treasury 20Y",
  ust_30y: "Treasury 30Y",
  tips: "TIPS",
  ig_credit: "IG credit",
  hy_credit: "HY credit",
};

export function assetLabel(id: string): string {
  return ASSET_LABELS[id] ?? id;
}

export const BENCHMARK_LABELS: Record<string, string> = {
  sixty_forty: "60/40",
  target_date: "Target-date glidepath",
  best_constant: "Best constant mix",
  none: "None",
};
