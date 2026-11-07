/**
 * Maps the shared research context onto study specifications, so "Run with current assumptions" on any
 * page builds a valid, hashed study spec. Fields a study does not use are ignored; a universe the study
 * cannot use (e.g. one without a 10Y Treasury) falls back to the study default and is reported.
 */
import type { StudyKind } from "@/lib/api/v2";
import type { ResearchContext } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
const HAS_10Y = ["core", "modern", "core_long_history", "core_duration", "liability_match"];
const HAS_30Y = ["modern", "core_duration", "pp_modern_etf", "pp_research_historical"];

export interface ContextSpec { spec: any; notes: string[] }

export function studySpecFromContext(kind: StudyKind, c: ResearchContext): ContextSpec {
  const notes: string[] = [];
  const scenario = { generator: c.generator, n_paths: c.nPaths, seed: c.seed };
  const investor = { age: c.retirementAge, retirement_age: c.retirementAge, horizon_years: c.horizonYears, initial_wealth: c.wealth,
    mortality: c.mortality, sex: c.sex };
  const prefs = { gamma: c.gamma, beta_annual: c.beta };
  const uni = (allowed: string[], fallback: string) => {
    if (allowed.includes(c.universe)) return c.universe;
    notes.push(`universe ${c.universe} is not usable by this study; using ${fallback}`);
    return fallback;
  };
  const costs = { commission_bps: 0.4 * c.costBps, half_spread_bps: 0.6 * c.costBps };
  switch (kind) {
    case "frontier":
      return { spec: { data: { universe: uni(HAS_10Y, "core_long_history") }, scenario, preferences: prefs, costs,
        investor: { ...investor, horizon_years: Math.max(c.horizonYears, 40) } }, notes };
    case "signed_flow":
      return { spec: { data: { universe: uni(HAS_10Y, "core_long_history") }, scenario: { ...scenario, n_paths: Math.min(c.nPaths, 3000) }, preferences: prefs }, notes };
    case "permanent":
      return { spec: { data: { universe: c.ppUniverse }, scenario, investor, preferences: prefs, costs, withdrawal: c.withdrawalRate }, notes };
    case "rebalance":
      return { spec: { data: { universe: uni(["core_duration", "core", "core_long_history", "modern", "liability_match"], "core_duration") }, scenario, investor,
        preferences: prefs, withdrawal: c.withdrawalRate, main_cost_bps: c.costBps }, notes };
    case "scenario_lab":
      return { spec: { data: { universe: uni(HAS_30Y.filter((u) => HAS_10Y.includes(u)), "core_duration") }, scenario, investor, withdrawal: c.withdrawalRate }, notes };
    case "asof":
      return { spec: { data: { universe: uni(HAS_10Y, "core_long_history") }, scenario: { ...scenario, generator: "markov_switching" }, investor,
        as_of: c.asOf || null }, notes };
    case "optimize":
      return { spec: { data: { universe: uni(["core_duration"], "core_duration") }, scenario, investor, preferences: prefs, costs, withdrawal: c.withdrawalRate }, notes };
    case "compare_v2":
      return { spec: { data: { universe: uni(["core_duration"], "core_duration") }, scenario, investor, preferences: prefs, costs, withdrawal: c.withdrawalRate,
        policies: c.comparePolicies.split(",").filter(Boolean), focus: c.compareFocus }, notes };
    case "multi_asset":
      return { spec: { data: { universe: uni(["multi_asset_public", "multi_asset_full"], "multi_asset_public") },
        scenario: { ...scenario, generator: c.generator === "markov_switching" || c.generator === "bootstrap" || c.generator === "student_t" ? c.generator : "markov_switching" },
        investor, preferences: prefs, costs, withdrawal: c.withdrawalRate }, notes };
    case "evidence":
      return { spec: { scenario: { generator: "bootstrap", n_paths: c.nPaths, seed: c.seed } }, notes };
  }
}
