import { v, type VizEntry } from "./define";

const CMP = "Policy comparison study (compare_v2) on the duration universe.";
const EV = "Evidence study (evidence), reading the latest completed studies.";
const VAL = "Validation job (/v1/validation/{run_id}) on a finished experiment.";

export const VALIDATION: VizEntry[] = [
  // ------------------------------------------------------------------ Strategy Comparison
  v("CO-01", "compare", "policies", "Paired CE forest plot", {
    q: "How does each policy's CE differ from the benchmark on identical paths?", what: "Paired ΔCE vs the benchmark with path-bootstrap 95% CIs, one row per policy.",
    x: "ΔCE vs benchmark", y: "Policy", units: "% of benchmark CE", series: "Diamonds = estimate; bars = CI; dotted = no difference.",
    calc: "Paired delta-method and path-pair bootstrap on common random numbers.", read: "CIs excluding zero are model-conditional differences.", why: "Same-path comparison removes sampling noise between policies.",
    hyp: ["H5", "H6"], method: ["ci", "utility"], data: CMP, related: ["CO-08"] }, ["mc", "ledger", "crra", "study"]),
  v("CO-02", "compare", "policies", "Paired path scatter", {
    q: "On how many individual paths does the focus policy beat the benchmark?", what: "Per-path CE of the benchmark (x) vs the focus policy (y); failures highlighted.", x: "Benchmark path CE", y: "Policy path CE",
    units: "real $/yr", series: "Dots = paths; crosses = a shortfall in either.", calc: "Path-level CE from path utilities.", read: "Points above the diagonal favour the policy.", why: "Shows whether average gains are broad or driven by a few paths.",
    method: ["utility"], data: CMP }, ["mc", "ledger", "study"]),
  v("CO-03", "compare", "policies", "Twin wealth / consumption fan", {
    q: "How do wealth and consumption distributions differ on the same innovations?", what: "Wealth and funded-consumption fans for the focus policy and the benchmark.", x: "Age", y: "Real wealth; consumption", units: "real US$",
    series: "Two banded fans.", calc: "Quantiles across shared paths.", read: "Compare medians and lower bands.", why: "Distributions, not just means.", method: ["wealth"], data: CMP }, ["mc", "ledger", "study"]),
  v("CO-04", "compare", "policies", "Divergent path explorer", {
    kind: "table", q: "Where do the policies differ most, and why?", what: "The five most negative and positive path differences with early-sequence explanations (first-5-year equity return, CPI) and shortfall timing.",
    other: "Table", units: "real $; %", series: "Two groups.", calc: "Rank paths by Δ path CE.", read: "Large differences coinciding with poor early equity returns reveal sequence risk.", why: "Explains averages.", method: ["shortfall"], data: CMP }, ["mc", "ledger", "study"]),
  v("CO-05", "compare", "history", "Cohort winner matrix", {
    q: "Which policy won for each actual historical start year?", what: "Path-CE of each policy relative to the benchmark for one cohort per start year.", x: "Cohort start year", y: "Policy", c: "Δ path CE", units: "%",
    series: "Diverging heatmap.", calc: "Historical cohorts, path-level CE.", read: "Runs of colour reflect overlapping cohorts.", why: "Tests policies on what actually happened.", method: ["scenarios"], data: CMP, related: ["PP-11"] }, ["hist", "ledger", "pub", "study"]),
  v("CO-06", "compare", "policies", "Trade-off table", {
    kind: "table", q: "How do policies trade off CE, survival, shortfall, drawdown and cost?", what: "Sortable table of CE, success, mean unmet spending, median drawdown, cost and data quality.", other: "Table",
    units: "mixed", series: "One row per policy.", calc: "From the shared simulation.", read: "Sort by the objective you care about.", why: "No single metric suffices.", method: ["utility"], data: CMP }, ["mc", "ledger", "study"]),
  v("CO-07", "compare", "attribution", "Attribution waterfall", {
    q: "How much of the CE change comes from allocation, spending rule, rebalancing and costs?", what: "Sequential and order-free (Shapley) attribution of the CE change across four factors.",
    x: "Factor", y: "CE change", units: "real $/yr", series: "Waterfall + Shapley vs sequential bars.", calc: "16 runs over factor coalitions; Shapley averages over orderings.",
    read: "Sequential attribution depends on order; Shapley does not and sums to the total.", why: "Separates the effect of spending rules from allocation.", method: ["utility"], data: CMP,
    lim: ["Guardrails change spending itself: this is a joint spending-plus-allocation comparison."] }, ["mc", "ledger", "study"]),
  v("CO-08", "compare", "robustness", "Regime robustness forest", {
    q: "Does the focus policy's advantage keep its sign across generators and calibration windows?", what: "ΔCE of the focus policy vs the benchmark under each generator and window.", x: "ΔCE", y: "Generator / window", units: "%",
    series: "Forest; sign reversals flagged in the page banner.", calc: "Re-simulation under each alternative.", read: "Mixed signs mean the ranking is model-dependent.", why: "Robustness to model choice.", hyp: ["H12"], method: ["scenarios"], data: CMP }, ["mc", "ledger", "study"]),
  v("CO-09", "compare", "robustness", "Model-source substitution sensitivity", {
    kind: "table", q: "Do public repriced and WRDS observed returns agree on the overlap?", what: "Mean difference, tracking error and correlation between sources for series with more than one source.", other: "Table",
    units: "% p.a.", series: "One row per series.", calc: "Overlap statistics.", read: "Unavailable until both sources exist.", why: "Quantifies proxy error.", method: ["data"], data: "Multi-source panel (needs WRDS)." }, ["pub"]),
  v("CO-10", "compare", "history", "Historical first-failure timeline", {
    q: "For the worst actual cohort, when did spending go unfunded?", what: "Desired vs funded spending and the unmet gap by year for the worst historical cohort.", x: "Years since start", y: "Real $ per year", units: "real US$",
    series: "Desired, funded, unmet (policy and benchmark).", calc: "Ledger on the historical cohort.", read: "Earlier unmet spending is more damaging.", why: "Grounds failure in a real history.", method: ["shortfall"], data: CMP }, ["hist", "ledger", "study"]),
  v("CO-11", "compare", "saved-runs", "Saved runs on common paths", {
    kind: "table", q: "How do two to four finished experiments compare when re-evaluated on the first run's paths?", what: "CE ± SE, paired ΔCE vs the first run, depletion probability and CVaR95 shortfall per policy.",
    other: "Table", units: "real $/yr; %", series: "One row per run.", calc: "Policies re-evaluated on the first run's scenario tensor (common random numbers).", read: "Only paired differences are comparable.",
    why: "First-class comparison of any saved experiments.", method: ["ci"], data: "A compare job over finished experiment runs.", related: ["CO-12"] }, ["legacy", "mc"]),
  v("CO-12", "compare", "saved-runs", "Saved-run paired path outcomes", {
    q: "On which paths does the second policy beat the first?", what: "Per-path CE of run #1 vs run #k with the equal line.", x: "#1 path CE", y: "#k path CE", units: "real $/yr",
    series: "Points = paths.", calc: "Path CE from path utilities on common paths.", read: "Share above the diagonal = share of paths favouring #k.", why: "Breadth of the gain.", method: ["utility"], data: "Compare job.", related: ["CO-02"] }, ["legacy", "mc"]),
  v("CO-13", "compare", "saved-runs", "Saved-run divergent paths", {
    q: "On paths where one policy depletes and the other survives, what happened?", what: "Wealth paths of both policies on a selected divergent path, with the first-10-year equity return.", x: "Age", y: "Real wealth",
    units: "real US$", series: "One line per policy.", calc: "Compare job divergent-path extraction.", read: "Early equity losses typically separate the policies.", why: "Explains failures.", method: ["shortfall"], data: "Compare job." }, ["legacy", "mc"]),

  // ------------------------------------------------------------------ Research & Evidence
  v("RS-01", "research", "hypotheses", "Hypothesis registry (H1–H12)", {
    kind: "table", q: "Which pre-registered hypotheses are supported, contradicted, fragile or not computed?",
    what: "Each hypothesis with its claim, test statistic, effect, 95% CI, Holm- and BH-adjusted p, data window, verdict, evidence grade, supporting run and notes.",
    other: "Table", units: "per statistic", series: "One row per hypothesis.", calc: "Automatic scoring of completed studies against pre-registered rules; Holm and BH over the computed family.",
    read: "'Supported' requires CI excluding zero, Holm-adjusted p ≤ 0.05 and materiality; 'not computed' is never inferred.", why: "Separates evidence from computation.",
    hyp: ["H1-v2", "H12"], method: ["ci"], data: EV, related: ["RS-02", "OV-05"] }, ["study"]),
  v("RS-02", "research", "hypotheses", "Evidence heatmap", {
    q: "On which robustness dimensions does each hypothesis pass?", what: "Hypotheses × six evidence dimensions; crosses = not computed.", x: "Dimension", y: "Hypothesis", c: "1 pass / 0.5 fragile / 0 fail", units: "status",
    series: "Matrix.", calc: "From the evidence study.", read: "'Robust' grade requires ≥ 4 passing dimensions.", why: "Shows where evidence is thin.", method: ["ci"], data: EV, related: ["OV-05"] }, ["study"]),
  v("RS-03", "research", "uncertainty", "Monte Carlo convergence", {
    q: "How many paths are needed for a stable estimate?", what: "60/40 success estimate and Wilson CI as paths increase, with the CI half-width and the automatic stop point.", x: "Paths", y: "P(success); half-width",
    units: "%; pp", series: "Estimate with CI; half-width line.", calc: "Re-simulation at increasing path counts.", read: "Stop when the half-width meets the precision target.", why: "Precision targets should be explicit.",
    method: ["ci"], data: EV }, ["mc", "ledger", "study"]),
  v("RS-04", "research", "uncertainty", "Threshold replication ridge", {
    q: "How variable is b_min across re-estimations?", what: "Distribution of b_min across joint bootstrap replicates for each withdrawal rate, with the share unidentified.", x: "b_min", y: "Withdrawal rate",
    units: "%", series: "One ridge per withdrawal rate.", calc: "From the frontier study bootstrap.", read: "Wide ridges or high unidentified shares mean the threshold is not stable.", why: "H12.", hyp: ["H12"], method: ["necessity"], data: EV, related: ["WL-02"] }, ["mc", "study"]),
  v("RS-05", "research", "oos", "Walk-forward scoreboard", {
    kind: "table", q: "Does a policy selected on past data hold up on later actual cohorts?", what: "Train window, test start, selected equity share, held-out CE, Δ vs 60/40, ex-post best and regret per split.",
    other: "Table", units: "real $; %", series: "One row per split.", calc: "Fit on data before the split; score on later historical cohorts.", read: "Low regret means the selection generalised.", why: "Chronological OOS is the strongest test.",
    hyp: ["H8"], method: ["ci"], data: EV }, ["hist", "study"]),
  v("RS-06", "research", "uncertainty", "Parameter and generator disagreement forest", {
    q: "How do conclusions move across assumptions and models?", what: "The frontier threshold forest and the comparison study's robustness forest together.", x: "b_min / ΔCE", y: "Assumption", units: "%",
    series: "Two forests.", calc: "From the frontier and compare studies.", read: "Look for sign reversals or infeasibility under alternatives.", why: "Disagreement is a result.", hyp: ["H12"], method: ["scenarios"], data: EV, related: ["WL-06", "CO-08"] }, ["mc", "study"]),
  v("RS-07", "research", "uncertainty", "Return-order permutation distribution", {
    q: "How much of the worst cohort's outcome is due to the order of returns?", what: "Terminal wealth of the worst actual cohort vs permutations of the same monthly returns.", x: "Terminal real wealth", y: "Count", units: "real US$",
    series: "Histogram + actual-order marker.", calc: "Random permutations of the cohort's months.", read: "An actual outcome in the far left tail means the sequence, not the average return, caused the failure.",
    why: "Isolates sequence risk.", method: ["shortfall"], data: EV, lim: ["Permutation destroys serial dependence: stylised attribution, not a historical counterfactual."] }, ["hist", "study"]),
  v("RS-08", "research", "data-quality", "Source and calendar coverage audit", {
    kind: "table", q: "Which data cover which windows, and what was dropped?", what: "Universe windows, dropped months and members; per-series coverage, missing months and content hashes.", other: "Tables",
    units: "dates; counts", series: "Universes and series.", calc: "From the panel and catalog.", read: "Missing months are dropped, never filled.", why: "Every sample restriction must be visible.", method: ["data"], data: EV }, ["registry"]),
  v("RS-09", "research", "oos", "Bias / leakage checklist", {
    kind: "table", q: "Do automated checks find look-ahead or leakage?", what: "Executed checks: future-return mutation, lagged regime signal, NBER exclusion, publication lags, ALFRED, pre-inception, distributions, oracle exclusion.",
    other: "Table", units: "status", series: "One row per check.", calc: "Run inside the evidence study.", read: "'warning' items are disclosed limitations.", why: "No look-ahead is a scientific invariant.", method: ["limits"], data: EV }, ["study"]),
  v("RS-10", "research", "conclusions", "Research conclusion builder", {
    kind: "panel", q: "Which verified claims can be cited, with what caveats?", what: "Markdown of computed hypotheses with statistics, CIs, adjusted p, verdicts, run IDs and caveats — no generative interpretation.",
    other: "Text", units: "–", series: "One bullet per hypothesis.", calc: "Generated from the registry rows.", read: "Never cite 'not computed' or conditional evidence as universal.", why: "Reproducible reporting.", method: ["repro"], data: EV }, ["study"]),
  v("RS-11", "research", "hypotheses", "Original H1–H4 tests", {
    kind: "panel", q: "Do the original lifecycle hypotheses H1–H4 survive their falsification rules?", what: "The original tests: H1 (DP slope under parameter bootstrap), H2 (sweep ΔCE), H3/H4 (attribution), each falsified or not with its statistic.",
    other: "Cards", units: "per test", series: "One card per hypothesis.", calc: "Uses the latest decumulation sweep and attribution run.", read: "'skipped' means an input run is missing.", why: "Preserves the original research programme.",
    hyp: ["H1-v2", "H2-v2", "H3-v2", "H4-v2"], method: ["dp", "ci"], data: "CE sweep + attribution runs." }, ["legacy"]),
  v("RS-12", "research", "validation", "Run validation: Monte Carlo convergence", {
    q: "Is a run's ΔCE stable as paths increase?", what: "ΔCE ± 2 SE of the selected run's policy vs benchmark at increasing path counts.", x: "Paths (log)", y: "ΔCE", units: "%", series: "Points with error bars.",
    calc: "Frozen policy re-evaluated on larger tensors.", read: "Error bars should shrink and the sign stay constant.", why: "First robustness layer.", method: ["ci"], data: VAL }, ["legacy", "mc"]),
  v("RS-13", "research", "validation", "Run validation: parameter uncertainty", {
    q: "Does ΔCE survive re-estimating the scenario model?", what: "Histogram of ΔCE across scenario models re-estimated on bootstrap resamples of history.", x: "ΔCE", y: "Count", units: "%", series: "Histogram.",
    calc: "Outer bootstrap of the calibration history.", read: "Mass on both sides of zero means the sign is parameter-dependent.", why: "Second robustness layer.", method: ["ci", "scenarios"], data: VAL }, ["legacy", "mc"]),
  v("RS-14", "research", "validation", "Run validation: model uncertainty", {
    q: "Does ΔCE survive changing the generator?", what: "ΔCE ± 2 SE of the frozen policy under each generator.", x: "Generator", y: "ΔCE", units: "%", series: "Bars.", calc: "Same policy, different generators.",
    read: "Mixed signs = model-dependent.", why: "Third robustness layer.", method: ["scenarios"], data: VAL }, ["legacy", "mc"]),
  v("RS-15", "research", "validation", "Run validation: sequence-risk isolation", {
    q: "How much of the worst benchmark cohort's outcome is due to return order?", what: "CE distributions of the policy and benchmark under permutations of the worst cohort's months, with actual-order markers.",
    x: "CE", y: "Count", units: "real $/yr", series: "Overlaid histograms; dotted = actual order.", calc: "Permutations of a fixed multiset of returns.", read: "Timing effect = actual − permuted mean.",
    why: "Isolates sequence risk for a run.", method: ["shortfall"], data: VAL }, ["legacy", "hist"]),
  v("RS-16", "research", "validation", "Run validation: calibration windows", {
    q: "Does ΔCE depend on the calibration window?", what: "ΔCE ± 2 SE of the frozen policy with the scenario model re-fitted on sub-periods.", x: "Window", y: "ΔCE", units: "%", series: "Bars.",
    calc: "Refits on sub-periods.", read: "Stable signs across windows support robustness.", why: "Structural breaks.", method: ["scenarios"], data: VAL }, ["legacy", "mc"]),
  v("RS-17", "research", "validation", "Run validation: tail coverage", {
    kind: "table", q: "Does the model reproduce joint tail events?", what: "Realised vs simulated probability of both equity and 10Y below their 10% quantile over 1/12/60 months.", other: "Table", units: "%",
    series: "Rows = horizons.", calc: "Historical frequency vs simulated frequency.", read: "Simulated far below realised means the model under-states joint risk.", why: "Tail calibration.", method: ["scenarios"], data: VAL }, ["legacy", "hist"]),
  v("RS-18", "research", "validation", "Run validation: historical cohort replay", {
    q: "How did the frozen policy and benchmark do on actual cohorts?", what: "Cohort CE of policy and benchmark by start date.", x: "Cohort start", y: "Cohort CE", units: "real $/yr", series: "Two lines.",
    calc: "Historical replay of the frozen policy.", read: "Cohorts overlap; read as a description, not a sample of independent trials.", why: "Grounds simulations in history.", method: ["scenarios"], data: VAL }, ["legacy", "hist"]),

  // ------------------------------------------------------------------ Runs & Reports
  v("RN-01", "runs", "registry", "Run registry", {
    kind: "table", q: "Which runs exist, in what state, on which data?", what: "Every run (experiments, sweeps, studies, comparisons, validations, attribution, hypotheses) with status, family, accounting semantics, data vintage, timestamps, cache hits and errors; table or timeline view.",
    other: "Table / timeline", units: "–", series: "One row per run.", calc: "Run registry.", read: "Select a run to inspect it; the timeline groups runs by day.", why: "Single audit surface.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-02", "runs", "registry", "Run inspector", {
    kind: "panel", q: "Exactly what produced this run?", what: "Spec JSON, seeds, lock hash, engine SHA, catalog, warnings, provenance, report exports and — for experiments — the full result summary.",
    other: "Panel", units: "–", series: "Selected run.", calc: "Registry + results.", read: "Two runs are comparable only with matching catalog and spec fields.", why: "Reproducibility.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-03", "runs", "registry", "Live execution progress", {
    kind: "panel", q: "Where is a running job?", what: "Server-sent progress stages with cancel and forced retry.", other: "Stage chips + log", units: "–", series: "Stages.", calc: "SSE from the registry.",
    read: "Progress is real backend state, never simulated.", why: "Long jobs need visibility.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-04", "runs", "figures", "Figure gallery (F1–F6)", {
    kind: "panel", q: "Which runs support each flagship figure?", what: "F1–F6 with study, run, status, evidence grade, failure reason and reproduce command.", other: "Cards", units: "–", series: "Six figures.",
    calc: "Figure registry.", read: "'not computed' figures must be run before citing.", why: "Paper traceability.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-05", "runs", "reproduce", "Compare saved runs (compatibility)", {
    kind: "panel", q: "Can two runs be compared directly?", what: "Compatibility check across kind, catalog, accounting semantics, universe, generator, seed, horizon and spending, with reasons and a remedy.",
    other: "Form + verdict", units: "–", series: "Two runs.", calc: "/v1/runs/compatibility.", read: "Incompatible runs need a paired re-run.", why: "Prevents invalid comparisons.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-06", "runs", "reproduce", "Export center", {
    kind: "panel", q: "How do I export results?", what: "Study JSON/CSV, experiment PDF/CSV/JSON/BibTeX, manifest and references.", other: "Links", units: "–", series: "Exports.", calc: "Derived data only.",
    read: "No raw WRDS rows are ever exported.", why: "Licence-aware reporting.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-07", "runs", "reproduce", "Reproduce command", {
    kind: "panel", q: "How do I re-execute this run?", what: "CLI and make commands with warnings if the data catalog or engine changed since the run.", other: "Commands", units: "–", series: "Selected run.",
    calc: "Compares run metadata with the server.", read: "A changed catalog yields a new run ID; the old run stays addressable.", why: "Determinism.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-08", "runs", "health", "Coverage / data health", {
    kind: "panel", q: "Is the data and test pipeline healthy?", what: "Series count, model-generated series, recorded tests and failed runs.", other: "KPIs + table", units: "counts", series: "Health indicators.", calc: "/v1/data/health.",
    read: "Failed runs show their reason; no figure is drawn from them.", why: "Operational integrity.", method: ["data"], data: "Panel + registry." }, ["registry"]),
  v("RN-09", "runs", "figures", "Paper build preview", {
    kind: "panel", q: "Is the paper buildable?", what: "Sections, missing figures, bibliography coverage and LaTeX tool availability.", other: "Text", units: "–", series: "paper/main.tex.", calc: "Static parse.",
    read: "Missing figures need make paper after seeding.", why: "Reporting pipeline.", method: ["repro"], data: "Repository paper sources." }, ["registry"]),
  v("RN-10", "runs", "health", "Audit trail", {
    kind: "table", q: "Who did what to which run?", what: "Append-only log of submits, cache hits, cancels, completions, failures, traces, exports and refreshes.", other: "Table", units: "timestamps", series: "Events.",
    calc: "Registry audit table.", read: "Credentials are never recorded.", why: "Governance.", method: ["repro"], data: "Run registry." }, ["registry"]),
  v("RN-11", "runs", "registry", "Run history timeline", {
    kind: "panel", q: "What was run on each day?", what: "Runs grouped by day with kind, IDs, catalog and headline CE.", other: "Timeline", units: "–", series: "Days.", calc: "Run registry.", read: "Click a run to inspect it.",
    why: "Chronological audit view.", method: ["repro"], data: "Run registry." }, ["registry"]),

  // ------------------------------------------------------------------ Methodology
  v("MT-01", "methodology", "pipeline", "Pipeline diagram", { kind: "panel", q: "How does data become a figure?", what: "Data → panel → scenarios → cash flows → allocation/spending/trading → utilities → inference → figures.",
    other: "Diagram", units: "–", series: "Stages.", calc: "Static architecture.", read: "Each stage maps to backend modules.", why: "Orientation.", method: ["repro"], data: "None." }),
  v("MT-02", "methodology", "pipeline", "Equation explorer", { kind: "panel", q: "Which equations does the engine implement?", what: "Ledger, utility, bond necessity, CIs, duration, rebalancing and regime-filter equations.",
    other: "Equations", units: "–", series: "Topics.", calc: "KaTeX rendering of the implemented formulas.", read: "Use 'Learn more' from a chart to land on its topic.", why: "Transparency.", method: ["wealth"], data: "None." }),
  v("MT-03", "methodology", "data", "Data dictionary", { kind: "table", q: "What is each series?", what: "Canonical ID, label, quantity, units, coverage, source, vintage, transformation and licence.", other: "Table", units: "–",
    series: "One row per series.", calc: "Series catalog.", read: "'model_generated' = repriced from yields.", why: "Provenance.", method: ["data"], data: "Series catalog." }, ["registry"]),
  v("MT-04", "methodology", "data", "Assumption registry", { kind: "table", q: "What are the defaults and where is their sensitivity studied?", what: "Documented decisions and every study default.", other: "Table", units: "–",
    series: "Decisions and defaults.", calc: "From the study spec models.", read: "Sensitivity columns point to the relevant analyses.", why: "Assumptions must be explicit.", method: ["limits"], data: "Study defaults." }),
  v("MT-05", "methodology", "references", "Research bibliography", { kind: "table", q: "Which sources support the methods?", what: "BibTeX entries and the methodological/data references used.", other: "Table + links", units: "–", series: "References.",
    calc: "Parsed from paper/references.bib.", read: "Follow links to the original sources.", why: "Scholarly grounding.", method: ["repro"], data: "paper/references.bib." }),
  v("MT-06", "methodology", "limitations", "Validation & model limitations", { kind: "table", q: "Where must interpretation stop?", what: "Unresolved limitations and prohibited interpretations.", other: "Table", units: "–", series: "Limitations.",
    calc: "Curated.", read: "Check before citing any result.", why: "Honest reporting.", method: ["limits"], data: "None." }),
  v("MT-07", "methodology", "reproduce", "Reproducible methods", { kind: "panel", q: "How do I reproduce everything?", what: "CLI/API recipes and each study's default spec.", other: "Code", units: "–", series: "Recipes.", calc: "Static + /v1/studies defaults.",
    read: "Specs are validated server-side.", why: "Reproducibility.", method: ["repro"], data: "Study defaults." }),
  v("MT-08", "methodology", "mathematics", "Mathematical notes", { kind: "panel", q: "How exactly is each quantity defined?", what: "Derivations for wealth dynamics, income, utility and SEs, shortfall, DP and parametric policies, generators, fixed income, data and limitations.",
    other: "Article", units: "–", series: "Sections.", calc: "Static derivations matching the engine.", read: "Anchors are the targets of 'Learn more' links.", why: "Technical reference.", method: ["wealth"], data: "Series catalog (data table)." }),
];
