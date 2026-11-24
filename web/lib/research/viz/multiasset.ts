import { v, type VizEntry } from "./define";

const MA = "Multi-asset study (multi_asset): public tier = US/intl/EM equity, 10Y/30Y Treasury, IG credit, G10 currency basket, T-bills (1990–); full tier adds TIPS, high yield, gold and commodities (WRDS).";
const TIER = ["The public tier has no gold, broad commodities or high-yield credit; the real & currency block is the G10 currency basket.",
  "Investment-grade credit in the public tier is repriced from the Moody's Aaa yield with no default or downgrade losses, which flatters credit-heavy mixes."];

export const MULTIASSET: VizEntry[] = [
  v("MA-01", "permanent", "multi-asset", "Asset-class coverage by data tier", {
    kind: "table", q: "Which asset classes exist in each data tier, from when, and from which source?",
    what: "Every sleeve of the two multi-asset universes with its asset class, building block, source, provenance (observed, index-derived or model-generated) and coverage.",
    other: "Table: sleeve, asset class, block, tier, provenance, source, first and last observation", units: "dates",
    series: "One row per sleeve; the full tier is listed even when it cannot be built (missing WRDS series are named).",
    calc: "Read from the series catalog and the universe definitions; nothing is simulated.",
    read: "A tier can only be used when every required sleeve exists. Never compare a public-tier result with a full-tier result as if they shared a sample: their windows differ.",
    why: "Asset-class conclusions are only as broad as the data behind them; this makes the coverage explicit.",
    method: ["data"], data: "Series catalog (GET /v1/catalog/series).", related: ["MA-02", "MT-03"], lim: TIER }, ["registry"]),
  v("MA-02", "permanent", "multi-asset", "Multi-asset Permanent Portfolio and static designs", {
    q: "How are the static multi-asset designs composed, sleeve by sleeve?",
    what: "Target weights of 60/40, equal weight, the multi-asset Permanent Portfolio (25% each to growth, duration, real & currency and cash) and static risk parity, stacked by sleeve.",
    x: "Policy", y: "Target weight", c: "Sleeve (asset)", units: "% of portfolio",
    series: "One stacked bar per static design; colours follow the asset, never its rank.",
    calc: "Building blocks group sleeves by asset class; inside a block sleeves are inverse-volatility weighted on the calibration window. Risk parity solves equal risk contributions on the calibration covariance.",
    read: "The Permanent Portfolio spreads capital evenly across economic roles, not across risk; risk parity spreads risk, so low-volatility sleeves (duration, cash-like) get more capital.",
    why: "It shows what each design actually holds before any performance comparison.", method: ["rebalancing"], data: MA, related: ["MA-03", "PP-01"], lim: TIER }, ["study"]),
  v("MA-03", "permanent", "multi-asset", "Static multi-asset designs vs 60/40", {
    kind: "table", q: "Do static multi-asset designs improve the retiree's welfare and survival over 60/40?",
    what: "CE, paired ΔCE vs 60/40 with a path-bootstrap 95% interval, 30-year success, median maximum drawdown and turnover for the static designs.",
    other: "Sortable table", units: "CE in real $/yr; ΔCE in % of the 60/40 CE; success and drawdown in %",
    series: "One row per static design, all on identical test paths.",
    calc: "Holdings ledger, fixed real 4% draw, annual calendar rebalancing with 1 bp commission and 2 bps half-spread; ΔCE paired across paths.",
    read: "A ΔCE interval entirely below zero means 60/40 delivers more welfare to this retiree under this model; lower drawdown alone is not a welfare gain.",
    why: "It is the direct test of the Permanent Portfolio idea across all asset classes, not just four sleeves.",
    hyp: ["H5"], method: ["utility", "ci"], data: MA, related: ["MA-04", "PP-02"], lim: TIER }, ["mc", "ledger", "crra", "study"]),
  v("MA-04", "optimize", "multi-asset", "Dynamic allocation policy family: ΔCE vs 60/40", {
    q: "Which allocation family — static, regime, trend, risk-based or utility-optimal — improves on 60/40 out of sample?",
    what: "Paired ΔCE of every policy against 60/40 on the test paths, with path-bootstrap 95% intervals, grouped by family.",
    x: "ΔCE vs 60/40", y: "Policy (family)", units: "% of the 60/40 certainty equivalent",
    series: "Markers are point estimates; bars are 95% intervals; the vertical line is no difference.",
    calc: "Fitted policies (regime, CRRA static, CRRA parametric) are chosen on training paths (seed set A) and scored here on disjoint test paths (seed set B).",
    tex: String.raw`\Delta_{\mathrm{CE}}=\mathrm{CE}(\pi)/\mathrm{CE}(\pi_{60/40})-1`,
    read: "Only intervals that exclude zero indicate a difference under this model; dynamic policies pay turnover costs that are already included.",
    why: "It ranks the dynamic allocation ideas on one common, cost-aware welfare scale.", hyp: ["H5", "H9"], method: ["utility", "ci", "rebalancing"], data: MA,
    related: ["MA-05", "MA-08", "MA-10"], lim: TIER }, ["mc", "ledger", "crra", "regime", "study"]),
  v("MA-05", "optimize", "multi-asset", "Welfare vs failure trade-off", {
    q: "Which policies buy survival at the cost of welfare, and which improve both?",
    what: "Each policy's 30-year failure probability against its certainty equivalent.",
    x: "P(unmet spending within 30 years)", y: "CE (real $/yr)", c: "Policy family", units: "%; real US$ per year",
    series: "One point per policy.", calc: "Both coordinates from the same test paths.",
    read: "Up and to the left is better on both objectives; a policy below and right of 60/40 is dominated.",
    why: "Welfare and survival can disagree; the plot shows where they do.", method: ["utility", "shortfall"], data: MA, related: ["MA-04", "OP-01"], lim: TIER }, ["mc", "ledger", "study"]),
  v("MA-06", "optimize", "multi-asset", "Dynamic weight path by asset class", {
    q: "How does a dynamic policy actually move across asset classes over retirement?",
    what: "Average holding of each sleeve at the start of each year across paths, for the selected policy.",
    x: "Years since retirement", y: "Average weight", c: "Sleeve", units: "% of portfolio",
    series: "Stacked bars sum to 100% each year.", calc: "Mean of the ledger's start-of-year post-trade weights across test paths.",
    read: "Averages hide path-by-path moves: a trend policy that is 50% cash on average may be fully invested on most paths and fully in cash on a few.",
    why: "It shows what the dynamic rule does, not just how it scores.", method: ["rebalancing"], data: MA, related: ["MA-04", "MA-07"], lim: TIER }, ["mc", "ledger", "study"]),
  v("MA-07", "optimize", "multi-asset", "Regime-conditional block weights", {
    q: "What does the regime-based policy hold in each point-in-time regime?",
    what: "Building-block weights the regime policy chose for each filtered regime on training paths, with the paired ΔCE by starting regime where enough paths start there.",
    x: "Regime", y: "Block weight", c: "Building block", units: "% of portfolio",
    series: "One stacked bar per regime.", calc: "Coordinate search over the block simplex (step 0.25), one regime at a time, maximising training-path CE.",
    read: "Weights identical across regimes mean the filter adds no decision value; regimes with fewer than 30 starting paths are reported but not interpreted.",
    why: "It tests whether the economic state should change the asset-class mix.", hyp: ["H3-v2"], method: ["posterior", "utility"], data: MA, related: ["MA-04", "PP-05"], lim: TIER }, ["mc", "regime", "study"]),
  v("MA-08", "optimize", "multi-asset", "Implementation cost of dynamic policies", {
    q: "How much trading do dynamic policies need, and is it paid back?",
    what: "Annual one-way turnover against paired ΔCE vs 60/40 for every policy.",
    x: "Turnover (one-way, per year)", y: "ΔCE vs 60/40", c: "Policy family", units: "multiples of wealth per year; %",
    series: "One point per policy.", calc: "Turnover summed over executed trades divided by wealth, from the holdings ledger; costs are already inside ΔCE.",
    read: "High-turnover policies must show a larger ΔCE to justify the trading; points far right and below zero are expensive and unhelpful.",
    why: "Dynamic allocation is only useful if it survives realistic execution.", method: ["rebalancing"], data: MA, related: ["MA-04", "RB-01"], lim: TIER }, ["mc", "ledger", "study"]),
  v("MA-09", "optimize", "multi-asset", "Saver vs retiree: who benefits?", {
    q: "Does the same allocation policy help an accumulating saver and a decumulating retiree equally?",
    what: "Paired ΔCE vs 60/40 for the retiree (CE of funded consumption) and for the saver (CE of total real resources after contributing), side by side.",
    x: "Policy", y: "ΔCE vs 60/40", c: "Investor", units: "%",
    series: "Two bars per policy.", calc: "Same frozen policies; the saver contributes a share of labour income until retirement, then draws.",
    read: "Policies that help the retiree by reducing risk often hurt the saver, whose horizon rewards growth assets.",
    why: "Allocation advice that ignores the investor's cash-flow direction can be wrong for half the lifecycle.", hyp: ["H1-v2"], method: ["utility", "income"], data: MA,
    related: ["LC-01", "MA-04"], lim: TIER }, ["mc", "ledger", "crra", "study"]),
  v("MA-10", "optimize", "multi-asset", "Robustness across scenario generators", {
    q: "Do the policy rankings survive a different model of returns?",
    what: "Paired ΔCE vs 60/40 of the same frozen policies under the main generator and under each robustness generator.",
    x: "ΔCE vs 60/40", y: "Policy · generator", units: "%",
    series: "Markers with 95% intervals; one row per policy and generator.",
    calc: "Policies fitted once on the main training paths are re-evaluated on paths from the other generator (no refitting).",
    read: "A sign that flips between generators means the conclusion is model-dependent.",
    why: "Separates model risk from Monte Carlo noise.", method: ["scenarios", "ci"], data: MA, related: ["MA-04", "CO-08"], lim: TIER }, ["mc", "ledger", "study"]),
];
