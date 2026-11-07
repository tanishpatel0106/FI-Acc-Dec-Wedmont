"use client";
import { create } from "zustand";

/**
 * Shared research context: one set of investor, scenario, policy and market assumptions used by the
 * lifecycle simulator, the optimiser and (through studySpecFromContext) every research study.
 */
export type UniverseKey = "core" | "modern" | "core_long_history" | "core_duration" | "pp_modern_etf" | "pp_research_historical" | "liability_match";

export interface BuilderState {
  universe: UniverseKey;
  generator: "historical" | "bootstrap" | "student_t" | "markov_switching" | "curve_factor";
  nPaths: number;
  seed: number;
  startAge: number;
  retirementAge: number;
  maxAge: number;
  wealth: number;
  income: number;
  savingsRate: number;
  pension: number;
  gamma: number;
  beta: number;
  eta: number;
  cMin: number;
  policy: string;
  spendingRule: "fixed_real" | "fixed_pct" | "guardrails" | "bucket" | "utility_optimal";
  withdrawalRate: number;
  rebalanceMonths: number;
  costBps: number;
  benchmark: "sixty_forty" | "target_date" | "best_constant" | "none";
  sex: "male" | "female" | "unisex";
  mortality: boolean;
  horizonYears: number;
  asOf: string;
  comparePolicies: string;   // comma-separated policy keys carried into Strategy Comparison
  compareFocus: string;
  ppUniverse: UniverseKey;
  set: (patch: Partial<BuilderState>) => void;
}

export const DEFAULTS = {
  universe: "core" as const,
  generator: "bootstrap" as const,
  nPaths: 2000,
  seed: 20261030,
  startAge: 65,
  retirementAge: 65,
  maxAge: 100,
  wealth: 1_000_000,
  income: 100_000,
  savingsRate: 0.1,
  pension: 20_000,
  gamma: 4,
  beta: 0.97,
  eta: 0,
  cMin: 6000,
  policy: "sixty_forty",
  spendingRule: "fixed_real" as const,
  withdrawalRate: 0.04,
  rebalanceMonths: 1,
  costBps: 0,
  benchmark: "sixty_forty" as const,
  sex: "unisex" as const,
  mortality: true,
  horizonYears: 30,
  asOf: "",
  comparePolicies: "sixty_forty,all_equity,forty_sixty,pp_ex_gold,equity_cash_buffer,target_date",
  compareFocus: "target_date",
  ppUniverse: "pp_modern_etf" as UniverseKey,
};

export const useResearchContext = create<BuilderState>((set) => ({
  ...DEFAULTS,
  set: (patch) => set(patch),
}));

/** Back-compatible name used by the simulator and optimiser components. */
export const useBuilder = useResearchContext;

export type ResearchContext = Omit<BuilderState, "set">;

export function specFromBuilder(s: Omit<BuilderState, "set">, policyOverride?: string) {
  return {
    data: { universe: s.universe === "core_long_history" || s.universe === "core_duration" || s.universe === "liability_match" ? "core" : s.universe === "core" || s.universe === "modern" ? s.universe : "core" },
    scenario: { generator: s.generator, n_paths: s.nPaths, seed: s.seed, n_train_paths: Math.min(1000, s.nPaths) },
    investor: {
      start_age: s.startAge,
      retirement_age: s.retirementAge,
      max_age: s.maxAge,
      initial_wealth: s.wealth,
      income: s.income,
      savings_rate: s.savingsRate,
      pension: s.pension,
      sex: s.sex,
      mortality: s.mortality,
    },
    preferences: { gamma: s.gamma, beta_annual: s.beta, eta: s.eta, c_min: s.cMin },
    policy: {
      type: policyOverride ?? s.policy,
      spending_rule: s.spendingRule,
      withdrawal_rate: s.withdrawalRate,
      rebalance_months: s.rebalanceMonths,
      cost_bps: s.costBps,
    },
    outputs: { benchmark: s.benchmark },
  };
}

const URL_KEYS: (keyof typeof DEFAULTS)[] = Object.keys(DEFAULTS) as (keyof typeof DEFAULTS)[];

export function builderToQuery(s: Omit<BuilderState, "set">): string {
  const p = new URLSearchParams();
  for (const k of URL_KEYS) {
    const v = s[k];
    if (v !== DEFAULTS[k]) p.set(k, String(v));
  }
  return p.toString();
}

export function builderFromQuery(q: URLSearchParams): Partial<BuilderState> {
  const out: Record<string, unknown> = {};
  for (const k of URL_KEYS) {
    const raw = q.get(k);
    if (raw === null) continue;
    const d = DEFAULTS[k];
    if (typeof d === "number") {
      const n = Number(raw);
      if (Number.isFinite(n)) out[k] = n;
    } else if (typeof d === "boolean") out[k] = raw === "true";
    else out[k] = raw;
  }
  return out as Partial<BuilderState>;
}
