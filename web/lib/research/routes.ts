/**
 * Route and page-guide registry: the single source of truth for the sidebar, the command bar, the
 * homepage application guide, the research-question navigator, and each page's sections and help.
 */
import type { StudyKind } from "@/lib/api/v2";

export type PageKey =
  | "overview" | "withdrawal" | "lifecycle" | "permanent" | "rebalance" | "optimize" | "fixedIncome" | "marketState"
  | "scenarios" | "compare" | "research" | "runs" | "methodology";

export type NavGroup = "Research Home" | "Lifecycle & Portfolio Planning" | "Markets & Risk Research" | "Research Validation";

export interface PageSection { id: string; title: string; summary: string }

export interface PageInfo {
  key: PageKey;
  path: string;
  name: string;
  group: NavGroup;
  icon: string;               // tabler icon name, resolved in the shell
  question: string;           // primary research question
  canDo: string[];            // what the user can do there
  analytics: string[];        // important analytics / visualization types
  goodResult: string;         // what a useful result looks like
  howTo: string[];            // "How to use this page"
  limitations: string[];      // interpretation & limitations block
  related: PageKey[];
  studies: StudyKind[];       // persisted study kinds the page reads (for status)
  sections: PageSection[];    // in-page research sections (?section=)
}

export const PAGES: PageInfo[] = [
  {
    key: "overview", path: "/", name: "Overview", group: "Research Home", icon: "IconLayoutDashboard",
    question: "Where should the researcher begin, and what has the project established so far?",
    canDo: ["See computed findings with uncertainty", "Pick the right page for a question", "Follow a guided research journey", "Check data and study coverage"],
    analytics: ["Verdict tiles", "Bond-necessity mini-contour", "Evidence matrix", "Pipeline timeline", "Coverage grid"],
    goodResult: "A finding with a confidence interval, benchmark, universe and run ID — or an explicit 'Not computed' with the action that computes it.",
    howTo: ["Read the status tiles: every number links to its run.", "Use 'What are you trying to find out?' to get a page sequence.", "Open a page card to start working."],
    limitations: ["Tiles summarise the latest completed run of each study; they are model-conditional, not advice."],
    related: ["withdrawal", "research", "runs"], studies: ["frontier", "signed_flow", "permanent", "rebalance", "optimize", "evidence"], sections: [],
  },
  {
    key: "withdrawal", path: "/withdrawal-lab", name: "Withdrawal Lab", group: "Lifecycle & Portfolio Planning", icon: "IconTable",
    question: "When do bonds improve retirement survival, at which withdrawal rates, and by how much?",
    canDo: ["Map survival over withdrawal rate × bond share", "Find the minimum bond share for a success target", "Compare CE-optimal and survival-optimal mixes",
      "Run certainty-equivalent utility sweeps (withdrawal × years to retirement)", "Inspect shortfall timing and severity", "Drill into a single simulated path"],
    analytics: ["Survival heatmap", "Bond-necessity frontier", "CE utility heatmaps", "Forest plots", "Shortfall distributions", "Path drilldown"],
    goodResult: "An identified b_min (or 'no feasible allocation') with a bootstrap interval, stable across generators and windows.",
    howTo: ["Start in Research Overview: click any heatmap cell for its CI and a path drilldown.", "Change horizon and success target with the selectors.",
      "Use Utility & Welfare for CE sweeps vs 60/40, target-date or best constant mix.", "Check Robustness before citing a threshold."],
    limitations: ["Survival is fixed-horizon and financial unless labelled 'while alive'.", "Thresholds depend on generator, window, horizon and spending rule.",
      "Public-mode Treasury returns are model-generated from yields."],
    related: ["lifecycle", "compare", "research", "fixedIncome"], studies: ["frontier"],
    sections: [
      { id: "overview", title: "Research Overview", summary: "Headline survival surface and threshold KPIs." },
      { id: "sustainability", title: "Withdrawal Sustainability", summary: "Survival curves and maximum sustainable withdrawal." },
      { id: "bond-necessity", title: "Bond Necessity", summary: "Minimum bond share, phase ranges and bond instruments." },
      { id: "utility", title: "Utility & Welfare", summary: "CE-optimal vs survival-optimal and CE utility sweeps." },
      { id: "outcomes", title: "Historical & Simulated Outcomes", summary: "First-shortfall timing and severity." },
      { id: "robustness", title: "Robustness & Sensitivity", summary: "Threshold sensitivity and model disagreement." },
      { id: "paths", title: "Path-Level Explorer", summary: "Funding gap on individual simulated paths." },
    ],
  },
  {
    key: "lifecycle", path: "/lifecycle-flows", name: "Lifecycle & Cash Flows", group: "Lifecycle & Portfolio Planning", icon: "IconArrowsExchange",
    question: "How should allocations change as the household transitions from saving to spending?",
    canDo: ["Configure an investor and run a lifecycle simulation", "Compare age-only, cash-flow-only and full policies out of sample",
      "Estimate how the optimal bond share responds to signed net flow", "Follow a synthetic household from saving to spending"],
    analytics: ["Interactive simulator with wealth/consumption fans", "q × age allocation surface", "Marginal-slope forest", "Funded-ratio map", "Policy transition map"],
    goodResult: "A slope of the optimal bond share in q whose CI excludes zero at fixed age — or a clear null.",
    howTo: ["Use the Interactive Lifecycle Simulator to run one investor end to end.", "Read the q × age surface; switch objective between CE and survival.",
      "Check Age vs Cash-Flow Policies for out-of-sample evidence."],
    limitations: ["In the q-surface age acts through horizon and survival only; the simulator adds labour income.", "Policies are fitted on training paths and scored on disjoint test paths."],
    related: ["withdrawal", "optimize", "compare", "permanent", "rebalance"], studies: ["signed_flow", "historical_replay"],
    sections: [
      { id: "overview", title: "Signed-Flow Allocation", summary: "Optimal bond share over planned q and age." },
      { id: "replay", title: "Historical Portfolio Replay", summary: "One dated investor month by month through history, with point-in-time decisions, trades and a forward continuation." },
      { id: "simulator", title: "Interactive Lifecycle Simulator", summary: "Investor builder, run, progress and full results." },
      { id: "policies", title: "Age vs Cash-Flow Policies", summary: "Restricted policies scored out of sample; marginal slopes." },
      { id: "funding", title: "Funding & Liquidity", summary: "Funded ratio on the real curve with mortality." },
      { id: "household", title: "Household Journey", summary: "Synthetic persona, transition map, contribution frontier." },
    ],
  },
  {
    key: "permanent", path: "/permanent-portfolio", name: "Permanent Portfolio", group: "Lifecycle & Portfolio Planning", icon: "IconSquares",
    question: "Do stocks, Treasuries, gold and cash provide superior resilience across withdrawal and inflation regimes?",
    canDo: ["Score the classic 25/25/25/25 portfolio against 60/40 on identical paths", "Test duration, TIPS, cash-buffer and gold ablations",
      "Inspect Browne 15/35 rebalancing events", "Send selected policies to Strategy Comparison"],
    analytics: ["Scorecard with paired CIs", "Conditional advantage heatmap", "Macro quadrants", "Simplex", "Shapley ablation", "Cohort race"],
    goodResult: "A paired ΔCE vs 60/40 whose CI excludes zero in a pre-specified state, after costs.",
    howTo: ["Check the gold-data banner first: without an observed gold series only gold-free variants run.", "Read the scorecard, then the conditional heatmap.",
      "Use 'Compare with 60/40' to continue in Strategy Comparison."],
    limitations: ["Gold enters only as an observed fund total return (WRDS GLD).", "Regime roles of the sleeves are hypotheses, not guarantees."],
    related: ["compare", "rebalance", "marketState"], studies: ["permanent", "multi_asset"],
    sections: [
      { id: "overview", title: "Portfolio & Scorecard", summary: "Sleeves, data availability and the paired scorecard." },
      { id: "conditional", title: "Regimes & Conditional Advantage", summary: "Where PP helps or hurts; gold's role." },
      { id: "composition", title: "Duration, Cash & Composition", summary: "Duration replacement, cash buffer, simplex, Shapley." },
      { id: "history", title: "History & Rebalancing", summary: "Browne band events and historical cohorts." },
      { id: "multi-asset", title: "Multi-Asset All-Weather", summary: "The Permanent Portfolio idea across all asset classes and data tiers." },
    ],
  },
  {
    key: "rebalance", path: "/rebalance", name: "Rebalancing & Execution", group: "Lifecycle & Portfolio Planning", icon: "IconScale",
    question: "How should portfolios rebalance and fund withdrawals while controlling costs?",
    canDo: ["Compare 16 trading rules on identical paths after costs", "Inspect every simulated trade and the sources-and-uses reconciliation",
      "Measure turnover saved by cash-flow-aware rebalancing", "Size liquidity buffers"],
    analytics: ["Efficiency frontier", "Cost heatmaps", "Trade audit ledger", "Runway fans", "Funding race"],
    goodResult: "A rule with positive net ΔCE vs annual calendar whose CI excludes zero and whose trades reconcile.",
    howTo: ["Start with the efficiency frontier.", "Open Trade Ledger to see the actual trades behind a rule.", "Use Costs & Thresholds to check cost sensitivity."],
    limitations: ["Allocation, spending and trading policies are separate; only trading changes here.", "Pre-tax only: no tax lots are modelled."],
    related: ["permanent", "optimize", "compare"], studies: ["rebalance"],
    sections: [
      { id: "overview", title: "Efficiency Frontier", summary: "Net ΔCE vs turnover by strategy family." },
      { id: "costs", title: "Costs & Thresholds", summary: "Cost grids, decomposition and event statistics." },
      { id: "cash-flows", title: "Cash Flows & Funding", summary: "Cash-flow rebalancing, funding orders, liquidity runway." },
      { id: "rules", title: "Decision Rules & Risk", summary: "No-trade rule audit and risk-budget drift." },
      { id: "ledger", title: "Trade Ledger", summary: "Weights, trades and sources-and-uses on one path." },
    ],
  },
  {
    key: "optimize", path: "/optimize", name: "Portfolio Optimization", group: "Lifecycle & Portfolio Planning", icon: "IconFlask2",
    question: "Which portfolio maximizes utility, survival, or another constrained objective?",
    canDo: ["Optimise the policy family (mean–variance, risk parity, mean–CVaR, CRRA, glidepaths, regime, parametric)", "Solve the reduced grid dynamic program",
      "Trace CE–survival Pareto sets and switch objectives", "Attribute utility to sleeves (Shapley)", "Check stability of the optimum"],
    analytics: ["ΔCE bars with paired SE", "DP policy surfaces", "Pareto frontier", "Shapley bars", "Uncertainty bands", "Tornado", "Optimiser trace"],
    goodResult: "An optimum reported as a range across resamples, generators and refits, with its holdout performance.",
    howTo: ["Set investor assumptions in the research context, then run the policy family.", "Use Dynamic Programming for the reduced-state benchmark.",
      "Read Uncertainty & Stability before quoting a single weight."],
    limitations: ["DP solves a reduced 3-asset annual problem; its gains are in-model.", "Oracle (latent-state) policies are bounds, not tradable."],
    related: ["withdrawal", "lifecycle", "compare"], studies: ["optimize", "multi_asset"],
    sections: [
      { id: "overview", title: "Objectives & Frontier", summary: "Pareto set and objective switch." },
      { id: "multi-asset", title: "Dynamic Multi-Asset Allocation", summary: "Regime, trend, risk-based and utility-optimal allocation across equity, rates, credit, currencies, commodities and cash." },
      { id: "policy-family", title: "Policy Family Optimizer", summary: "Static, glidepath, regime and parametric policies vs 60/40." },
      { id: "dynamic", title: "Dynamic Programming & Policies", summary: "Grid DP surfaces and holdout policy classes." },
      { id: "surfaces", title: "Policy Surfaces", summary: "Regime and funding-ratio optimal weights." },
      { id: "attribution", title: "Attribution & Risk Budgets", summary: "Shapley and marginal utility, risk contributions." },
      { id: "robustness", title: "Uncertainty & Stability", summary: "Uncertainty band, tornado, optimiser trace." },
    ],
  },
  {
    key: "fixedIncome", path: "/fixed-income", name: "Fixed Income & Credit", group: "Markets & Risk Research", icon: "IconWaveSine",
    question: "How do duration, interest rates, inflation, credit spreads and liability matching affect portfolio risk?",
    canDo: ["Explore nominal/real curves and their PCA", "Measure duration, DV01, convexity and key-rate risk", "Shock the curve (parallel and twists)",
      "Value a real liability and build a cash-flow-matching ladder", "Inspect credit spreads and stock–bond co-loss"],
    analytics: ["Yield curves", "Key-rate bars", "Taylor vs full repricing", "Twist grids", "Return decomposition", "Liability PV", "Ladder", "Co-loss panel"],
    goodResult: "A liability-relative key-rate gap or a duration choice justified by its effect on survival in Withdrawal Lab.",
    howTo: ["Pick a curve date and withdrawal stream in the controls.", "Use Duration & Rate Risk for shocks.", "Go to Liability Matching for PV and ladders."],
    limitations: ["GSW curves are model fits (monthly).", "Bond-level credit analysis needs WRDS bond data."],
    related: ["marketState", "withdrawal", "scenarios"], studies: ["frontier"],
    sections: [
      { id: "curves", title: "Yield Curves", summary: "Curves, history and PCA factors." },
      { id: "risk", title: "Duration & Rate Risk", summary: "Duration/DV01/convexity, key rates, shocks and twists." },
      { id: "returns", title: "Bond Returns", summary: "Return decomposition and bond value across withdrawal rates." },
      { id: "liabilities", title: "Liability Matching", summary: "Real liability PV, duration gap and ladders." },
      { id: "credit", title: "Credit & Co-loss", summary: "Spreads, co-loss regimes and credit surface." },
    ],
  },
  {
    key: "marketState", path: "/market-state", name: "Market State", group: "Markets & Risk Research", icon: "IconActivity",
    question: "What do the latest available public and WRDS observations imply for the current market environment?",
    canDo: ["See observation, publication and retrieval dates per source", "Replay any month as-of with publication lags", "Compare conditional and unconditional scenarios"],
    analytics: ["Source ribbon", "Curves", "Breakeven & term premium", "Rolling correlation", "Filtered regimes", "Conditional fans"],
    goodResult: "A clearly dated view of the latest observations and how the observed starting state shifts survival.",
    howTo: ["Check the ribbon for staleness first.", "Set an as-of month to replay history.", "Run the as-of study for conditional scenarios."],
    limitations: ["Daily/monthly data, not a live feed.", "ALFRED real-time vintages are not ingested."],
    related: ["fixedIncome", "scenarios", "withdrawal"], studies: ["asof"],
    sections: [
      { id: "snapshot", title: "Current Snapshot", summary: "Sources, curves, decomposition and valuation." },
      { id: "dependence", title: "Correlation & Regimes", summary: "Rolling correlation and filtered regimes." },
      { id: "releases", title: "Data Releases & Credit", summary: "Release timeline, credit, ETF proxies, refresh audit." },
      { id: "conditional", title: "Conditional Scenarios", summary: "As-of conditional vs unconditional outcomes." },
    ],
  },
  {
    key: "scenarios", path: "/scenarios", name: "Scenarios & Risk", group: "Markets & Risk Research", icon: "IconChartDots3",
    question: "What do historical data, Monte Carlo models, regimes, correlations and stresses imply for future outcomes?",
    canDo: ["Analyse historical returns, drawdowns, volatility and correlation", "Study dependence (DCC, copulas, joint losses) and factor exposures",
      "Inspect Markov regimes", "Compare scenario generators and their diagnostics", "Run stress and shock-timing experiments"],
    analytics: ["Return moments", "Drawdowns", "Correlation heatmaps", "DCC", "Copula tails", "Regime probabilities", "Factor regressions", "Generator diagnostics", "Stress matrix"],
    goodResult: "A generator that passes its diagnostics, and stress results that are labelled model-generated.",
    howTo: ["Start with Historical Market Analytics; pick a universe.", "Use Dependence & Correlation for an asset pair.", "Check Scenario Generators and Model Diagnostics before trusting a simulation."],
    limitations: ["Stress scenarios are synthetic counterfactuals.", "Overlapping cohorts are not independent."],
    related: ["marketState", "withdrawal", "research"], studies: ["scenario_lab"],
    sections: [
      { id: "historical-analytics", title: "Historical Market Analytics", summary: "Moments, drawdowns, volatility and correlation." },
      { id: "dependence", title: "Dependence & Correlation", summary: "Rolling/DCC correlation, joint losses, copulas, forecasts." },
      { id: "factors", title: "Factor Models", summary: "Fama–French factor exposures." },
      { id: "regimes", title: "Market Regimes", summary: "Markov-switching probabilities, means and transitions." },
      { id: "generators", title: "Scenario Generators", summary: "Generator diagnostics, distributions, fans, cohorts." },
      { id: "stress", title: "Stress Testing", summary: "Stress matrix, shock timing, inflation scatter." },
      { id: "diagnostics", title: "Model Diagnostics", summary: "PIT and QLIKE mismatch diagnostics." },
    ],
  },
  {
    key: "compare", path: "/compare", name: "Strategy Comparison", group: "Research Validation", icon: "IconGitCompare",
    question: "How do portfolio policies perform on identical return and cash-flow paths?",
    canDo: ["Build a policy comparison on shared paths", "Compare saved runs by ID on common random numbers", "Attribute ΔCE to allocation, spending, rebalancing and costs",
      "Check robustness across generators, windows and data sources"],
    analytics: ["Paired forest", "Path scatter", "Twin fans", "Divergent paths", "Cohort winner matrix", "Attribution waterfall", "Robustness forest"],
    goodResult: "A paired difference with a CI that keeps its sign across generators and windows.",
    howTo: ["Choose policies in the comparison builder (or arrive from Permanent Portfolio).", "Use Saved-Run Comparison to compare any finished experiments.",
      "Check Robustness & Sources for sign reversals."],
    limitations: ["Joint spending-plus-allocation comparisons are labelled as such.", "Cohort results overlap."],
    related: ["permanent", "research", "runs"], studies: ["compare_v2"],
    sections: [
      { id: "policies", title: "Policies on Shared Paths", summary: "Comparison builder, paired results, fans and divergent paths." },
      { id: "saved-runs", title: "Saved-Run Comparison", summary: "Pick finished runs and compare them on common paths." },
      { id: "history", title: "Historical Cohorts", summary: "Cohort winners and first-failure timeline." },
      { id: "attribution", title: "Attribution", summary: "Allocation / spending / rebalancing / cost attribution." },
      { id: "robustness", title: "Robustness & Sources", summary: "Generators, windows and source substitution." },
    ],
  },
  {
    key: "research", path: "/research", name: "Research & Evidence", group: "Research Validation", icon: "IconMicroscope",
    question: "Which hypotheses have empirical support, which are inconclusive, and how robust are the results?",
    canDo: ["Read the H1–H12 registry with adjusted p-values", "Run the original H1–H4 tests", "Validate any run (convergence, parameter bootstrap, generators, cohorts)",
      "Check walk-forward OOS, permutation and leakage results", "Export verified conclusions"],
    analytics: ["Hypothesis registry", "Evidence heatmap", "Convergence", "Threshold ridge", "Walk-forward", "Permutation", "Leakage checklist"],
    goodResult: "A hypothesis verdict with an estimate, CI, adjusted p, data window and supporting run ID.",
    howTo: ["Run the other studies first, then the evidence study.", "Use Run Validation for a single experiment's robustness.", "Export the conclusion builder for a report."],
    limitations: ["Verdicts are model-conditional.", "Non-significance is not equivalence."],
    related: ["runs", "compare", "methodology"], studies: ["evidence"],
    sections: [
      { id: "hypotheses", title: "Hypotheses", summary: "H1–H12 registry, evidence matrix and H1–H4 tests." },
      { id: "validation", title: "Run Validation", summary: "Convergence, parameter, model, sequence and cohort checks for a run." },
      { id: "uncertainty", title: "Statistical Uncertainty", summary: "MC convergence, threshold ridge, disagreement, permutation." },
      { id: "oos", title: "Out-of-Sample & Leakage", summary: "Walk-forward and leakage checklist." },
      { id: "data-quality", title: "Data Quality", summary: "Source and calendar coverage audit." },
      { id: "conclusions", title: "Conclusions", summary: "Verified claims with run IDs." },
    ],
  },
  {
    key: "runs", path: "/runs", name: "Runs & Reports", group: "Research Validation", icon: "IconHistory",
    question: "How can a study be inspected, reproduced, compared, exported, or included in a paper?",
    canDo: ["Search all runs (experiments, sweeps, studies, comparisons, validations)", "Inspect specs, seeds, hashes and results", "Watch progress, cancel or retry",
      "Export PDF/CSV/JSON/BibTeX", "Reproduce a run and preview the paper"],
    analytics: ["Run registry", "Run inspector", "Progress stream", "Figure gallery", "Audit trail"],
    goodResult: "A run whose reproduce command returns identical results under the same data catalog.",
    howTo: ["Filter the registry and select a run.", "Use Reproduce & Export for the command and files.", "Figures & Paper lists F1–F6 with their runs."],
    limitations: ["Runs under different catalogs or accounting semantics are flagged as not directly comparable."],
    related: ["research", "methodology", "compare"], studies: [],
    sections: [
      { id: "registry", title: "Run Registry", summary: "All runs, inspector and live progress." },
      { id: "reproduce", title: "Reproduce & Export", summary: "Compatibility, reproduce command and exports." },
      { id: "figures", title: "Figures & Paper", summary: "F1–F6 gallery and paper build preview." },
      { id: "health", title: "Data Health & Audit", summary: "Data health and audit trail." },
    ],
  },
  {
    key: "methodology", path: "/methodology", name: "Methodology & Data", group: "Research Validation", icon: "IconBook2",
    question: "What mathematics, assumptions, datasets and implementation decisions support the research?",
    canDo: ["Read the equations behind every metric", "Look up any series in the data dictionary", "Check assumptions and limitations", "Find references and reproduction recipes",
      "Look up the explanation of any visualization"],
    analytics: ["Pipeline diagram", "Equation explorer", "Data dictionary", "Assumption registry", "Bibliography", "Visualization reference"],
    goodResult: "Every figure traceable to an equation, a dataset and an assumption.",
    howTo: ["Use 'Learn more' in any chart's info panel to land on the right section.", "Use the Visualization Reference to browse all chart explanations."],
    limitations: ["See Limitations: cases where interpretation is prohibited."],
    related: ["runs", "research"], studies: [],
    sections: [
      { id: "pipeline", title: "Pipeline & Equations", summary: "Pipeline diagram and equation explorer." },
      { id: "mathematics", title: "Mathematical Notes", summary: "Detailed derivations of the engine." },
      { id: "data", title: "Data & Assumptions", summary: "Data dictionary and assumption registry." },
      { id: "references", title: "References", summary: "Bibliography." },
      { id: "limitations", title: "Limitations", summary: "Validation and prohibited interpretations." },
      { id: "reproduce", title: "Reproducible Methods", summary: "CLI/API recipes and default specs." },
      { id: "visualizations", title: "Visualization Reference", summary: "Every chart's explanation, searchable." },
    ],
  },
];

export const PAGE_BY_KEY: Record<PageKey, PageInfo> = Object.fromEntries(PAGES.map((p) => [p.key, p])) as Record<PageKey, PageInfo>;
export const NAV_GROUPS: NavGroup[] = ["Research Home", "Lifecycle & Portfolio Planning", "Markets & Risk Research", "Research Validation"];

export function pageHref(key: PageKey, section?: string, anchor?: string): string {
  const p = PAGE_BY_KEY[key];
  return p.path + (section ? "?section=" + section : "") + (anchor ? "#" + anchor : "");
}

/** Research-question navigator (homepage). */
export interface ResearchQuestion {
  id: string;
  question: string;
  start: { page: PageKey; section?: string };
  next: { page: PageKey; section?: string }[];
  charts: string[];          // viz IDs to look at
  configure: string;         // expected experiment / input configuration
}

export const QUESTIONS: ResearchQuestion[] = [
  { id: "bonds-useful", question: "At what withdrawal rate do bonds become useful?", start: { page: "withdrawal", section: "overview" },
    next: [{ page: "withdrawal", section: "bond-necessity" }, { page: "withdrawal", section: "robustness" }, { page: "research", section: "hypotheses" }],
    charts: ["WL-01", "WL-02", "WL-06", "WL-10"], configure: "Bond-frontier study: horizon 30y, success target 90%, bootstrap generator; compare alternative generators in robustness." },
  { id: "pp-vs-6040", question: "Does a 60/40 portfolio outperform a Permanent Portfolio?", start: { page: "permanent", section: "overview" },
    next: [{ page: "permanent", section: "conditional" }, { page: "compare", section: "policies" }, { page: "research", section: "hypotheses" }],
    charts: ["PP-02", "PP-03", "PP-12", "CO-01"], configure: "Permanent Portfolio study at 4% withdrawal; the classic portfolio needs an observed gold series (WRDS GLD)." },
  { id: "multi-asset", question: "Should allocation move dynamically across equity, rates, credit, currencies and commodities?", start: { page: "optimize", section: "multi-asset" },
    next: [{ page: "permanent", section: "multi-asset" }, { page: "rebalance", section: "costs" }, { page: "research", section: "hypotheses" }],
    charts: ["MA-04", "MA-08", "MA-09", "MA-10"], configure: "Multi-asset study: public tier by default (1990–); after the WRDS ingest set data.universe to multi_asset_full for gold, commodities and high yield." },
  { id: "historical-investor", question: "How would one investor's portfolio have evolved through 2008, 2020 and 2022 — and what next?", start: { page: "lifecycle", section: "replay" },
    next: [{ page: "lifecycle", section: "replay" }, { page: "rebalance", section: "ledger" }, { page: "compare", section: "history" }],
    charts: ["HR-01", "HR-08", "HR-10", "HR-11"], configure: "Historical replay preset: age 20 in January 2007, $10,000, $45,000 salary, 15% saved, retire at 65, γ = 4; monthly decisions, 5-point bands." },
  { id: "rebalance", question: "How should I rebalance a retirement portfolio?", start: { page: "rebalance", section: "overview" },
    next: [{ page: "rebalance", section: "costs" }, { page: "rebalance", section: "ledger" }, { page: "compare", section: "robustness" }],
    charts: ["RB-01", "RB-05", "RB-03", "RB-04"], configure: "Rebalancing study: fixed 55/35/10 target, 4% withdrawal, 5 bps per side; vary only the trading rule." },
  { id: "inflation", question: "What happens to portfolio survival during inflationary regimes?", start: { page: "scenarios", section: "regimes" },
    next: [{ page: "scenarios", section: "stress" }, { page: "permanent", section: "conditional" }, { page: "marketState", section: "conditional" }],
    charts: ["SC-22", "SC-09", "PP-03", "MS-10"], configure: "Markov-switching generator (k = 2); stress library inflation and stagflation shocks; as-of conditional study." },
  { id: "age-vs-flow", question: "Should the allocation depend more on age or on cash flow?", start: { page: "lifecycle", section: "overview" },
    next: [{ page: "lifecycle", section: "policies" }, { page: "optimize", section: "dynamic" }, { page: "research", section: "hypotheses" }],
    charts: ["LC-01", "LC-02", "LC-03", "OP-15"], configure: "Signed-flow study (q from −15% to +10%, ages 25–85); grid DP for the reduced-state benchmark." },
  { id: "duration", question: "How much interest-rate duration is appropriate?", start: { page: "fixedIncome", section: "liabilities" },
    next: [{ page: "fixedIncome", section: "risk" }, { page: "fixedIncome", section: "returns" }, { page: "permanent", section: "composition" }],
    charts: ["FI-10", "FI-04", "FI-12", "PP-07"], configure: "Set the withdrawal stream and horizon; compare liability duration with key-rate exposures and bond-instrument survival effects." },
  { id: "oos", question: "Which policy has the strongest out-of-sample evidence?", start: { page: "research", section: "oos" },
    next: [{ page: "optimize", section: "dynamic" }, { page: "lifecycle", section: "policies" }, { page: "compare", section: "robustness" }],
    charts: ["RS-05", "OP-06", "LC-02", "CO-08"], configure: "Evidence study after the other studies; chronological walk-forward splits 1975/1990/2005." },
  { id: "reproduce", question: "How can I reproduce a research exhibit?", start: { page: "runs", section: "figures" },
    next: [{ page: "runs", section: "registry" }, { page: "runs", section: "reproduce" }, { page: "methodology", section: "reproduce" }],
    charts: ["RN-04", "RN-02", "RN-07"], configure: "Pick a figure, open its run, copy the reproduce command (python -m lifecycle.cli reproduce <run_id>)." },
];

export interface WorkflowStage { stage: string; description: string; pages: PageKey[] }

export const WORKFLOW: WorkflowStage[] = [
  { stage: "Data", description: "Public snapshot or WRDS panel: coverage, provenance, vintages.", pages: ["methodology", "marketState"] },
  { stage: "Market Analysis", description: "Curves, correlation, regimes and factor structure.", pages: ["marketState", "fixedIncome", "scenarios"] },
  { stage: "Scenarios", description: "Fit generators, check diagnostics, run stresses.", pages: ["scenarios"] },
  { stage: "Lifecycle Simulation", description: "Investor cash flows, spending rules, survival and CE.", pages: ["lifecycle", "withdrawal"] },
  { stage: "Optimization", description: "Policies by objective; DP; Permanent Portfolio variants; trading rules.", pages: ["optimize", "permanent", "rebalance"] },
  { stage: "Comparison", description: "Paired comparisons on identical paths; attribution.", pages: ["compare"] },
  { stage: "Statistical Validation", description: "H1–H12, convergence, OOS, leakage, robustness.", pages: ["research"] },
  { stage: "Research Report", description: "Run IDs, reproduction, exports and the paper.", pages: ["runs", "methodology"] },
];

export interface Journey { title: string; steps: { page: PageKey; section?: string; goal: string }[] }

export const JOURNEYS: Journey[] = [
  { title: "Historical Investor Journey", steps: [
    { page: "lifecycle", section: "replay", goal: "Replay a 20-year-old from January 2007, month by month, through the crises." },
    { page: "lifecycle", section: "replay", goal: "Inspect any month: state, signals, target, trades and costs." },
    { page: "compare", section: "history", goal: "Compare policies on the same investor and history." },
    { page: "research", section: "oos", goal: "Check cohorts, start years and windows before trusting a ranking." }] },
  { title: "Retirement Sustainability Research", steps: [
    { page: "withdrawal", section: "overview", goal: "Locate where bonds become necessary and how sure we are." },
    { page: "lifecycle", section: "simulator", goal: "Check the same investor across accumulation and decumulation." },
    { page: "compare", section: "policies", goal: "Compare candidate policies on identical paths." },
    { page: "research", section: "hypotheses", goal: "See whether the evidence supports the claim." }] },
  { title: "Portfolio Construction Research", steps: [
    { page: "marketState", section: "snapshot", goal: "Establish the current, dated market state." },
    { page: "permanent", section: "overview", goal: "Test the four-sleeve defensive design." },
    { page: "rebalance", section: "overview", goal: "Choose an implementable trading rule after costs." },
    { page: "optimize", section: "overview", goal: "Trade off CE against survival and constraints." },
    { page: "compare", section: "robustness", goal: "Confirm the ranking survives model changes." }] },
  { title: "Quantitative Model Validation", steps: [
    { page: "scenarios", section: "generators", goal: "Check that each generator reproduces history." },
    { page: "research", section: "uncertainty", goal: "Quantify MC, parameter and model uncertainty." },
    { page: "runs", section: "reproduce", goal: "Reproduce and export the exact run." },
    { page: "methodology", section: "pipeline", goal: "Document equations, data and limitations." }] },
];
