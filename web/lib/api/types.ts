// Response payloads (mirrors backend/lifecycle/runs/summarize.py and friends)

export type Quantiles = { p05: number[]; p25: number[]; p50: number[]; p75: number[]; p95: number[]; mean: number[] };

export interface CEBlock { ce: number; se: number }
export interface DeltaBlock { delta: number; se: number; z: number; significant: boolean }

export interface Shortfall {
  p_depletion: number;
  p_infeasible: number;
  mean_L: number;
  cvar95_L: number;
  p_depleted_by_age: number[];
  median_depletion_age: number | null;
  depletion_age_quantiles?: number[];
  retire_month: number;
}

export interface ExperimentResults {
  kind?: string;
  ages: number[];
  assets: string[];
  ce: { policy: CEBlock; benchmark?: CEBlock; delta?: DeltaBlock };
  fan: Record<string, Quantiles>;
  shortfall?: Shortfall;
  benchmark_shortfall?: Shortfall;
  terminal_wealth?: Quantiles;
  weights_path: { assets: string[]; mean: number[][] };
  risky_share?: Quantiles;
  q_path?: Quantiles;
  turnover_annual?: number;
  survival?: number[];
  n_paths?: number;
  sample?: { path_ce_policy: number[]; path_ce_benchmark?: number[]; depleted_policy: boolean[]; depleted_benchmark?: boolean[] };
  policy: Record<string, unknown> & { label: string; type?: string; theta?: number[] };
  benchmark: Record<string, unknown> & { name: string; label?: string };
  benchmarks?: Record<string, DeltaBlock & { label: string }>;
  scenario?: Record<string, unknown>;
  universe?: { name: string; assets: string[]; window: string[]; excluded?: Record<string, string>; provenance?: Record<string, string> };
  surfaces?: DPSurfaces;
  h1?: { regime: number; age: number; slope: number }[];
  timings?: Record<string, number>;
  warnings?: string[];
  meta?: Record<string, string>;
}

export interface DPSurfaces {
  x: number[];
  ages: number[];
  by_regime: { age: number; equity: number[]; bonds: number[]; bills: number[]; consumption_rate: number[]; q: number[] }[][];
}

export interface RunStatus {
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  stage: string;
  progress: number;
  kind: string;
  label?: string | null;
  parent_id?: string | null;
  spec?: Record<string, unknown>;
  timings?: Record<string, number> | null;
  warnings?: string[] | null;
  error?: string | null;
  created_at?: string;
  finished_at?: string | null;
  summary?: Record<string, unknown> | null;
}

export interface RunRow {
  run_id: string;
  kind: string;
  status: string;
  stage: string;
  progress: number;
  label: string | null;
  parent_id: string | null;
  spec_hash: string;
  catalog_hash: string | null;
  engine_version: string;
  created_at: string;
  finished_at: string | null;
  summary: Record<string, unknown> | null;
  error: string | null;
}

export interface SweepCell {
  run_id: string;
  x: number;
  y: number;
  ce: number;
  ce_se: number;
  policy: string;
  theta: number[] | null;
  p_depletion: number;
  p_depletion_benchmark: number | null;
  benchmarks: Record<string, DeltaBlock & { label: string }>;
  weights: Record<string, number> | null;
}

export interface Surface {
  kind: "decumulation" | "accumulation";
  x: number[];
  y: number[];
  x_label: string;
  y_label: string;
  cells: SweepCell[][];
  matrices: Record<string, { delta: number[][]; se: number[][] }>;
  shortfall: number[][];
  shortfall_benchmark: (number | null)[][];
  benchmarks: string[];
  summary: Record<string, unknown> & { mean_delta: number; max_delta: number; generator: string; gamma: number; universe: string };
}
