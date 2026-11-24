/**
 * Visualization-information registry: types, shared assumption/limitation presets and the entry builder.
 * Static text explains the chart; dynamic provenance (run ID, catalog, universe, window) is injected at
 * render time from the backend result, never written here.
 */
import type { PageKey } from "@/lib/research/routes";

export interface MethodLink { label: string; href: string }

export interface VizEntry {
  id: string;
  page: PageKey;
  section: string;
  title: string;
  kind: "chart" | "table" | "panel" | "diagram";
  researchQuestion: string;
  plainEnglishExplanation: string;
  axes: { x?: string; y?: string; color?: string; other?: string };
  units: string;
  seriesMeaning: string;
  calculationMethod: string;
  formula?: string;
  howToInterpret: string;
  whyItMatters: string;
  assumptions: string[];
  limitations: string[];
  relatedHypotheses: string[];
  methodologyLinks: MethodLink[];
  dataRequirements: string;
  related: string[];
}

export const REQUIRED_FIELDS: (keyof VizEntry)[] = [
  "id", "title", "researchQuestion", "plainEnglishExplanation", "axes", "units", "seriesMeaning", "calculationMethod",
  "howToInterpret", "whyItMatters", "assumptions", "limitations", "relatedHypotheses", "methodologyLinks", "dataRequirements",
];

type Tag = "mc" | "ledger" | "legacy" | "pub" | "hist" | "curve" | "crra" | "macro" | "regime" | "synthetic" | "study" | "registry";

const PRESET: Record<Tag, { a?: string; l?: string }> = {
  mc: { a: "Paths come from the selected scenario generator fitted on the stated calibration window; every policy in the chart shares the same paths (common random numbers).",
    l: "Monte Carlo confidence intervals are conditional on the fitted model; parameter and model uncertainty are reported separately (Robustness sections)." },
  ledger: { a: "Holdings-ledger accounting: planned flows first, then the trading decision, then next-month returns; costs are charged on executed notional and unmet spending is booked, never consumed." },
  legacy: { a: "Target-weight lifecycle kernel (the original engine): flows at the start of the month, proportional rebalancing cost on weight turnover, consumption floor booked as an explicit shortfall.",
    l: "Runs from the target-weight kernel and the holdings ledger use different accounting conventions; compare them only through the compatibility check in Runs & Reports." },
  pub: { l: "Without WRDS, Treasury, TIPS and investment-grade returns are repriced from public constant-maturity yields (model-generated), not observed total returns." },
  hist: { l: "Overlapping historical windows share most of their months and are not independent observations; the history contains few independent long-horizon outcomes." },
  curve: { a: "Fed GSW (Gürkaynak–Sack–Wright) fitted zero curves at month end; par yields are derived from the zeros.", l: "Curves are smooth model fits, not traded quotes; the real curve starts in 1999 and is held flat beyond 20 years." },
  crra: { a: "CRRA utility of funded real consumption with risk aversion γ and mortality-weighted discounting; a utility floor applies to utility only and is never counted as funded spending." },
  macro: { l: "Macro series are latest vintages with publication lags; ALFRED real-time vintages are not ingested, so revised series are descriptive only." },
  regime: { a: "Regimes come from a Gaussian Markov-switching model estimated by EM; decisions use filtered (or lagged) probabilities, never smoothed or latent states.",
    l: "Regime labels are descriptive names assigned after estimation; regime counts and labels can change with the sample window." },
  synthetic: { l: "Stress paths are synthetic, model-generated counterfactuals layered on bootstrap paths — not historical observations." },
  study: { a: "Values come from one persisted, hashed study run; identical specifications reproduce identical results (make reproduce RUN=<id>)." },
  registry: { a: "Read directly from the run registry and data catalog; no simulation is performed to draw this view." },
};

const METHOD: Record<string, MethodLink> = {
  wealth: { label: "Wealth & ledger equations", href: "/methodology?section=pipeline&topic=wealth" },
  utility: { label: "Utility and CE", href: "/methodology?section=pipeline&topic=utility" },
  necessity: { label: "Bond-necessity definition", href: "/methodology?section=pipeline&topic=necessity" },
  ci: { label: "Confidence intervals", href: "/methodology?section=pipeline&topic=ci" },
  duration: { label: "Bond pricing & duration", href: "/methodology?section=pipeline&topic=duration" },
  rebalancing: { label: "Rebalancing & costs", href: "/methodology?section=pipeline&topic=rebalancing" },
  posterior: { label: "Regime filter", href: "/methodology?section=pipeline&topic=posterior" },
  income: { label: "Labour income & pension", href: "/methodology?section=mathematics#m-income" },
  shortfall: { label: "Spending shortfall", href: "/methodology?section=mathematics#m-shortfall" },
  dp: { label: "Dynamic programming & parametric policies", href: "/methodology?section=mathematics#m-dp" },
  scenarios: { label: "Scenario generators", href: "/methodology?section=mathematics#m-scenarios" },
  fi: { label: "Fixed-income mathematics", href: "/methodology?section=mathematics#m-fi" },
  data: { label: "Data dictionary", href: "/methodology?section=data" },
  limits: { label: "Limitations", href: "/methodology?section=limitations" },
  repro: { label: "Reproducible methods", href: "/methodology?section=reproduce" },
};

export interface EntryInput {
  q: string; what: string; x?: string; y?: string; c?: string; other?: string; units: string; series: string;
  calc: string; tex?: string; read: string; why: string; as?: string[]; lim?: string[]; hyp?: string[];
  method?: string[]; data: string; related?: string[]; kind?: VizEntry["kind"];
}

export function v(id: string, page: PageKey, section: string, title: string, e: EntryInput, tags: Tag[] = []): VizEntry {
  const assumptions = [...tags.map((t) => PRESET[t].a).filter(Boolean) as string[], ...(e.as ?? [])];
  const limitations = [...tags.map((t) => PRESET[t].l).filter(Boolean) as string[], ...(e.lim ?? [])];
  return {
    id, page, section, title, kind: e.kind ?? "chart", researchQuestion: e.q, plainEnglishExplanation: e.what,
    axes: { x: e.x, y: e.y, color: e.c, other: e.other }, units: e.units, seriesMeaning: e.series, calculationMethod: e.calc,
    formula: e.tex, howToInterpret: e.read, whyItMatters: e.why,
    assumptions: assumptions.length ? assumptions : ["See the methodology page for the model behind this view."],
    limitations: limitations.length ? limitations : ["Model-conditional research output; not personalised advice."],
    relatedHypotheses: e.hyp ?? [], methodologyLinks: (e.method ?? ["limits"]).map((m) => METHOD[m] ?? METHOD.limits),
    dataRequirements: e.data, related: e.related ?? [],
  };
}
