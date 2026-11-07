import { v, type VizEntry } from "./define";

const PP = "Permanent Portfolio study (permanent). Classic PP needs an observed gold fund series (WRDS GLD); otherwise only gold-free variants run on core_duration.";
const RB = "Rebalancing study (rebalance): fixed 55/35/10 target, fixed-real spending, 16 trading strategies.";
const OP = "Multi-objective study (optimize) on the duration universe.";

export const PORTFOLIO: VizEntry[] = [
  // ------------------------------------------------------------------ Permanent Portfolio
  v("PP-01", "permanent", "overview", "Classic four-sleeve matrix", {
    kind: "table", q: "What does each Permanent Portfolio sleeve hold, why, and how does it actually behave?",
    what: "The four sleeves (stocks, long Treasuries, gold, cash) with their 25% targets, average actual weights, stated purpose, measured exposures and exact data source.",
    other: "Table", units: "weights %; volatility % p.a.; betas unitless", series: "One row per sleeve; unavailable sleeves state why.",
    calc: "Exposures on the calibration window: real volatility, equity beta of real returns, inflation beta of nominal returns.",
    read: "Compare each sleeve's stated role with its measured betas — roles are hypotheses, not guarantees.", why: "It grounds the PP narrative in data.",
    hyp: ["H5"], method: ["data"], data: PP, related: ["PP-02", "PP-06"] }, ["pub", "study"]),
  v("PP-02", "permanent", "overview", "Policy comparison scorecard", {
    kind: "table", q: "How do PP variants compare with 60/40 on identical paths, spending and costs?",
    what: "CE, paired ΔCE vs the benchmark with path-bootstrap CI, success, Δsuccess, tail shortfall, drawdown, cost and turnover for each policy.",
    other: "Table", units: "CE real $/yr; Δ in %; costs bps/yr", series: "One row per policy; ΔCE vs 60/40.",
    calc: "Ledger simulation on one shared tensor; paired ΔCE with 200 path-pair bootstrap replicates.",
    read: "Prefer rows whose ΔCE CI excludes zero and whose success does not fall; check costs and drawdown alongside.", why: "This is flagship F3.",
    hyp: ["H5", "H11"], method: ["utility", "ci"], data: PP, related: ["CO-01"] }, ["mc", "ledger", "crra", "pub", "study"]),
  v("PP-03", "permanent", "conditional", "Conditional advantage heatmap", {
    q: "In which withdrawal rates and starting regimes does the PP beat (or trail) the benchmark?",
    what: "Paired ΔCE of the reference PP vs the benchmark by withdrawal rate and starting regime; crosses mark CIs including zero.",
    x: "Withdrawal rate", y: "Starting regime (or all starts)", c: "ΔCE vs benchmark (diverging)", units: "% of CE",
    series: "Rows: unconditional and per starting regime.", calc: "Separate tensors started in each regime's history pool; paired ΔCE with bootstrap CI.",
    read: "Blue cells without crosses are robust advantages; red cells are robust disadvantages.", why: "H5 asks whether PP wins in specified states.",
    hyp: ["H5"], method: ["ci", "posterior"], data: PP, related: ["PP-06"] }, ["mc", "ledger", "regime", "study"]),
  v("PP-04", "permanent", "conditional", "Macro regime quadrants", {
    q: "How did each sleeve and portfolio perform in growth × inflation quadrants historically?",
    what: "Mean annualised real return per sleeve in each quadrant, classified with information available at the time (lagged), with ±1.96 SE bars and month counts.",
    x: "Quadrant", y: "Mean real return (annualised)", units: "%", series: "Bars per sleeve.",
    calc: "INDPRO YoY (lag 2m) and CPI YoY (lag 1m) vs expanding medians (min 10y).", read: "Wide error bars and few months mean weak evidence; no asset ranking is implied.",
    why: "It tests the PP's 'four economic seasons' story against data.", method: ["data"], data: "Observed universe history and FRED INDPRO/CPI.", related: ["PP-01"],
    lim: ["SEs assume independence and understate uncertainty for persistent regimes."] }, ["hist", "macro"]),
  v("PP-05", "permanent", "conditional", "Dynamic PP weight river", {
    q: "How would a regime-adaptive PP shift its sleeves over time?",
    what: "Expected weights by year = share of paths in each filtered regime state × the per-regime weights fitted on training paths.",
    x: "Year", y: "Expected weight", units: "%", series: "Stacked by sleeve; table shows per-regime weights.",
    calc: "Coordinate search over a defensive grid (equity fixed at 25%) per regime on training paths.", read: "Shifts reflect how often the signal changes state, not a forecast.",
    why: "It tests whether conditioning helps the PP (H8).", hyp: ["H8"], method: ["posterior"], data: PP, related: ["OP-06"] }, ["mc", "regime", "study"]),
  v("PP-06", "permanent", "conditional", "Gold marginal utility and hedge effect", {
    q: "What does gold add to the PP, and does it hedge equity losses or inflation?",
    what: "Paired ΔCE of PP vs PP-without-gold by starting regime, plus descriptive hedge statistics (loss probability in equity's worst decile, CPI correlations by inflation regime).",
    x: "ΔCE from gold", y: "Start condition", units: "% of CE; probabilities; correlations", series: "Forest of ΔCE with CIs; KPI cards.",
    calc: "Paired comparison on shared paths; hedge statistics on observed overlap with lagged inflation classification.", read: "CIs crossing zero mean gold's value is not established.",
    why: "Gold is the PP's most debated sleeve.", hyp: ["H5"], method: ["ci"], data: PP, related: ["PP-12"], lim: ["Unavailable without an observed gold series."] }, ["mc", "study"]),
  v("PP-07", "permanent", "composition", "Long-bond duration replacement", {
    q: "Does the PP's long-bond sleeve need to be long?",
    what: "CE, success, tail shortfall, modified duration and DV01 when the long-Treasury sleeve is replaced by 2/5/10/30Y (cash and gold held constant).",
    x: "Sleeve maturity", y: "CE", units: "real $/yr; duration in years; DV01 $ per $1m per bp", series: "Bars = CE; table = risk metrics.",
    calc: "Ledger simulation per variant; duration/DV01 from the latest GSW curve for a par bond.", read: "If CE barely changes but DV01 rises, duration adds risk without welfare.",
    why: "H7: duration matters beyond bond share.", hyp: ["H7"], method: ["duration"], data: PP, related: ["FI-12"] }, ["mc", "ledger", "pub", "curve", "study"]),
  v("PP-08", "permanent", "composition", "Cash buffer trade-off", {
    q: "Does holding years of withdrawals in bills reduce early shortfall, and at what cost?",
    what: "First-10-year shortfall probability and CE by reserve size, paired against no buffer, with the median terminal-wealth sacrifice.",
    x: "Reserve (years of withdrawals)", y: "P(shortfall in first 10 years)", units: "%; real $", series: "Line + table of ΔCE with CI.",
    calc: "Cash-first funding with a reserve target refilled at annual rebalancing.", read: "A buffer is worth it only if early shortfall falls without a significant CE loss.",
    why: "H11 tests liability-matched buffers.", hyp: ["H11"], method: ["rebalancing"], data: PP, related: ["RB-08"] }, ["mc", "ledger", "study"]),
  v("PP-09", "permanent", "composition", "Defensive-mix simplex", {
    q: "With equity fixed at 25%, how should the other 75% be split between long bonds, gold and cash?",
    what: "Ternary plot of CE or success over the bond/gold/cash split; masked points need data the universe lacks.",
    other: "Ternary axes: long bond, gold, cash shares of the defensive 75%", c: "CE or P(success)", units: "real $/yr or %",
    series: "Each point is a full simulation with the Browne rule.", calc: "Ledger simulation per simplex point on the shared tensor.",
    read: "Look for a broad high region rather than a single best point.", why: "It separates defensive composition from equity exposure.", hyp: ["H4-v2"], data: PP, method: ["rebalancing"], related: ["PP-12"] }, ["mc", "ledger", "study"]),
  v("PP-10", "permanent", "history", "Browne band rule events", {
    q: "When does the Browne 15/35 rule trade, and what does it trade?",
    what: "Monthly pre-trade sleeve weights on one path with the 15%/35% bands, annual review dates and executed restoring trades; the table lists each trade.",
    x: "Years since retirement", y: "Actual sleeve weight", units: "%; real $", series: "Dotted = bands; ticks = reviews; dashed = trades.",
    calc: "Single-path ledger trace; the rule checks once a year and restores all sleeves to target on a breach.",
    read: "A breach between reviews does not trade in the classic rule; monthly monitoring is a different strategy.", why: "It makes the rule auditable.",
    method: ["rebalancing"], data: PP, related: ["RB-02"] }, ["ledger", "study"]),
  v("PP-11", "permanent", "history", "Historical cohort PP race", {
    q: "Across actual starting dates, how did the PP fare relative to the benchmark?",
    what: "Terminal real wealth of PP variants divided by the benchmark's, by actual cohort start.", x: "Cohort start", y: "Terminal wealth / benchmark", units: "ratio",
    series: "One line per variant; dotted line at 1.", calc: "Historical cohorts of the cohort horizon on the study universe.", read: "Above 1 the PP finished richer; long runs above or below reflect shared overlapping years.",
    why: "It checks simulations against what actually happened.", method: ["scenarios"], data: PP, related: ["CO-05"] }, ["hist", "ledger", "pub"]),
  v("PP-12", "permanent", "composition", "Ablation / Shapley panel", {
    q: "How much does each defensive sleeve contribute to CE, accounting for interactions?",
    what: "Shapley CE contributions and stand-alone gains of gold, nominal duration, real duration and cash, with the interaction term.",
    x: "Sleeve", y: "CE contribution", units: "real $/yr", series: "Shapley vs stand-alone bars.",
    calc: "Exact Shapley over coalitions; empty coalition = 100% equity; coalition S = 25% equity + 75% split equally over S.",
    tex: String.raw`\phi_i=\sum_{S\subseteq N\setminus\{i\}}\frac{|S|!(n-|S|-1)!}{n!}\big[v(S\cup\{i\})-v(S)\big]`,
    read: "Shapley values sum to v(full) − v(empty); a large interaction term means sleeves work together, not additively.", why: "It attributes the PP's value to its parts.",
    hyp: ["H4-v2", "H5"], method: ["utility"], data: PP, related: ["OP-03"] }, ["mc", "ledger", "study"]),
  v("PP-robust", "permanent", "composition", "Robust PP (minimax regret)", {
    q: "Which defensive mix is least regretted across scenario models?",
    what: "Maximum regret across generators for each candidate defensive mix; the chosen mix minimises it.", x: "Candidate", y: "Maximum regret", units: "% of best CE",
    series: "Points per candidate.", calc: "Regret = (best CE under a generator − CE of the candidate)/best CE; max over generators.", read: "Lower is more robust to model choice.",
    why: "Protects against over-fitting to one scenario model.", hyp: ["H12"], method: ["scenarios"], data: PP, related: ["OP-07"] }, ["mc", "study"]),

  // ------------------------------------------------------------------ Rebalancing
  v("RB-01", "rebalance", "overview", "Rebalancing efficiency frontier", {
    q: "Which trading rules improve net welfare relative to annual rebalancing, after costs?",
    what: "Paired ΔCE vs annual calendar against one-way rebalancing turnover per year, by strategy family, plus a forest of ΔCE CIs.",
    x: "One-way turnover per year", y: "ΔCE vs annual calendar", units: "%", series: "Marker shape = family; hover shows Δsuccess and CI.",
    calc: "All strategies on one tensor with identical targets and spending; costs on executed notional.", read: "Up-and-left is better: more welfare for less trading.",
    why: "Flagship F4.", hyp: ["H6"], method: ["rebalancing", "ci"], data: RB, related: ["RB-05", "RB-10"] }, ["mc", "ledger", "pub", "study"]),
  v("RB-02", "rebalance", "ledger", "Target vs actual weight paths", {
    q: "How far do weights drift from target between trades?",
    what: "Monthly pre-trade weights vs targets on one path for the chosen strategy; ticks mark executed rebalances.", x: "Years", y: "Weight", units: "%",
    series: "Solid = actual; dotted = target (reserve-adjusted when a buffer applies).", calc: "Single-path ledger trace.",
    read: "Wide drift with few trades is cheap but risky; tight tracking costs turnover.", why: "It shows what each rule tolerates.", method: ["rebalancing"], data: RB, related: ["RB-03"] }, ["ledger", "study"]),
  v("RB-03", "rebalance", "ledger", "Trade audit timeline", {
    kind: "table", q: "Which trades were executed, why, and at what cost?",
    what: "Every executed trade on the path: month, trigger, dollar trades per sleeve, pre/post weights, cost, net draw and wealth after.",
    other: "Table", units: "real $; %", series: "One row per trading event.", calc: "Single-path ledger trace.",
    read: "Check that triggers match the rule and costs match the traded notional.", why: "Results must be traceable to actual trades.", method: ["rebalancing"], data: RB, related: ["RB-04"] }, ["ledger", "study"]),
  v("RB-04", "rebalance", "ledger", "Sources and uses waterfall", {
    q: "Does the ledger reconcile on this path?",
    what: "Start wealth + market P&L + contributions − funded spending − trading cost = end wealth, with the residual shown explicitly.",
    x: "Component", y: "Real $", units: "real US$", series: "Waterfall bars; residual is reconciliation error.",
    calc: "Market P&L computed independently from post-trade holdings × returns.", read: "A residual near zero (rounding) confirms the accounting.",
    why: "Accounting identities are a scientific invariant.", method: ["wealth"], data: RB, related: ["RB-03"] }, ["ledger", "study"]),
  v("RB-05", "rebalance", "costs", "Calendar × threshold × cost heatmaps", {
    q: "How do cadence and band width interact with trading costs?",
    what: "Paired ΔCE vs buy-and-hold at the same cost, for calendar cadences and absolute bands across per-side costs.", x: "Per-side cost (bps)", y: "Cadence or band", c: "ΔCE", units: "% of CE",
    series: "Two heatmaps.", calc: "Ledger simulations on the shared tensor at each cost.", read: "Rules whose advantage turns negative as cost rises are cost-fragile.",
    why: "Implementation cost can erase rebalancing benefits.", hyp: ["H6"], method: ["rebalancing"], data: RB, related: ["RB-10"] }, ["mc", "ledger", "study"]),
  v("RB-06", "rebalance", "cash-flows", "Cash-flow rebalance savings", {
    q: "How much turnover is saved by routing contributions and withdrawals to under/overweight sleeves?",
    what: "Turnover of annual calendar rebalancing with proportional flows vs cash-flow targeting, for contributors, zero flow and withdrawers, with percentiles of saving per path.",
    x: "Flow scenario", y: "One-way turnover per year", units: "%", series: "Bars + table of saved turnover and ΔCE.",
    calc: "Same targets and returns; only the funding order changes.", read: "Savings should be largest when flows are large relative to drift.",
    why: "Flows are a free rebalancing tool.", hyp: ["H6"], method: ["rebalancing"], data: RB, related: ["RB-11"] }, ["mc", "ledger", "study"]),
  v("RB-07", "rebalance", "rules", "No-trade / trade decision breakdown", {
    kind: "panel", q: "How often does the utility-net-of-cost rule trade, and does it help on holdout paths?",
    what: "Accepted and rejected decisions per path and holdout ΔCE vs annual and monthly calendars.", other: "KPI cards", units: "counts; % of CE",
    series: "Accepted, rejected, holdout ΔCE.", calc: "Trade iff ½γ·d′Σd·12·W exceeds the estimated cost; Σ from the calibration window.",
    read: "Per-decision error rates are not identified; judge the rule by holdout ΔCE.", why: "A principled no-trade region should beat naive rules.", method: ["rebalancing"], data: RB }, ["mc", "ledger", "study"]),
  v("RB-08", "rebalance", "cash-flows", "Liquidity runway fan", {
    q: "How many months of withdrawals are held in bills over retirement, and does it protect against shortfall?",
    what: "Fan of runway months (T-bill holdings / monthly desired draw) for the largest and smallest reserve, with a table linking reserve size to shortfall and CE.",
    x: "Years since retirement", y: "Runway (months)", units: "months", series: "Two fans + table.", calc: "Cash-first funding with annual refills.",
    read: "A runway that collapses early means the buffer is spent before markets recover.", why: "It sizes cash buffers against sequence risk.", hyp: ["H11"], method: ["rebalancing"], data: RB, related: ["PP-08"] }, ["mc", "ledger", "study"]),
  v("RB-09", "rebalance", "costs", "Rebalancing event statistics", {
    q: "How often and how much does each rule trade?",
    what: "Median rebalances per year by strategy, with percentiles and median one-way trade size per event.", x: "Rebalances per year", y: "Strategy", units: "count; %",
    series: "Bars + table.", calc: "Per-path trade counts and turnover per event.", read: "Few large trades vs many small trades have different cost profiles.", why: "Trading frequency drives costs and operational burden.",
    method: ["rebalancing"], data: RB }, ["mc", "ledger", "study"]),
  v("RB-10", "rebalance", "costs", "Implementation-cost decomposition", {
    q: "Where do trading costs come from, and how much CE do they cost?",
    what: "Commission, half-spread and slippage in bps of wealth per year, and the CE drag vs the same strategy at zero cost.", x: "bps per year / ΔCE", y: "Strategy", units: "bps; % of CE",
    series: "Stacked cost bars; drag bars.", calc: "Costs accumulated from executed notional; drag = paired ΔCE vs zero-cost run.",
    read: "Pre-tax only; no after-tax claims are made.", why: "Separates explicit costs from lost growth.", method: ["rebalancing"], data: RB }, ["mc", "ledger", "study"]),
  v("RB-11", "rebalance", "cash-flows", "Withdrawal funding race", {
    q: "Which asset should fund withdrawals: proportional, cash-first, overweight-first or bond-ladder-first?",
    what: "Success and mean funded spending across withdrawal rates for four funding orders.", x: "Withdrawal rate", y: "P(success); funded spending", units: "%; real $",
    series: "One line per funding order.", calc: "Calendar 12m rebalancing with the funding order changed.", read: "The order matters most at high withdrawal rates.",
    why: "Funding order is an implementation choice with welfare consequences.", method: ["rebalancing"], data: RB, related: ["RB-06"] }, ["mc", "ledger", "study"]),
  v("RB-12", "rebalance", "rules", "Risk-budget drift", {
    q: "How does ex-ante portfolio risk drift away from target without rebalancing?",
    what: "Median ex-ante volatility of drifted weights vs target over time, and the duration contribution, for several rules; the info lists the lagged-estimate validation.",
    x: "Years since retirement", y: "Ex-ante volatility; duration contribution", units: "% p.a.; years", series: "One line per rule; dotted = target.",
    calc: "σ = √(w′Σw·12) with Σ from the calibration window; validation compares trailing-60m forecasts with realised next-12m volatility.",
    read: "Buy-and-hold drifts towards equity risk in rising markets.", why: "Risk budgets are what rebalancing protects.", method: ["rebalancing"], data: RB }, ["mc", "ledger", "study"]),

  // ------------------------------------------------------------------ Optimization
  v("OP-01", "optimize", "overview", "CE–survival Pareto frontier", {
    q: "Which static mixes are not dominated in CE and failure probability?",
    what: "Every static sleeve mix on a simplex grid in (failure probability, CE) space; Pareto points highlighted; shaded region violates the success constraint.",
    x: "P(failure, fixed horizon)", y: "CE", units: "%; real $/yr", series: "Grey = dominated; coloured = Pareto.", calc: "Ledger simulation per mix on one tensor.",
    read: "Move along the Pareto set to trade CE for safety; points in the shaded area fail the target.", why: "Makes the objective choice explicit.", hyp: ["H9"], method: ["utility"], data: OP, related: ["OP-07"] }, ["mc", "ledger", "crra", "study"]),
  v("OP-02", "optimize", "surfaces", "Optimal weight surfaces", {
    q: "How does the CE-optimal equity share vary with withdrawal rate and starting regime, and with q and age?",
    what: "Two heatmaps: CE-optimal equity share by withdrawal × starting regime (this study) and risky share by q × age (signed-flow study).",
    x: "Withdrawal rate / q", y: "Start regime / age", c: "Equity or risky share", units: "%", series: "Optimised grid choices.", calc: "Grid search over equity shares per cell.",
    read: "Compare with a fixed 60% to see where optimisation matters.", why: "It shows state dependence of the optimum.", hyp: ["H3-v2", "H1-v2"], method: ["utility", "posterior"], data: OP, related: ["LC-01"] }, ["mc", "regime", "study"]),
  v("OP-03", "optimize", "attribution", "Risk / utility contribution", {
    q: "How much CE does each non-equity sleeve contribute?",
    what: "Shapley CE of each sleeve (40% equity base) with path-bootstrap CIs, and the paired ΔCE of adding 10% to 60/40.", x: "CE contribution / ΔCE", y: "Sleeve", units: "real $/yr; %",
    series: "Two forests.", calc: "Exact Shapley over sleeve coalitions; 60 path resamples for CIs.", read: "Sleeves whose CI excludes zero add value under this model.",
    why: "H4 tests whether extra sleeves help.", hyp: ["H4-v2"], method: ["utility", "ci"], data: OP, related: ["PP-12", "OP-11"] }, ["mc", "ledger", "study"]),
  v("OP-04", "optimize", "robustness", "Policy uncertainty band", {
    q: "How uncertain is the 'optimal' equity share?",
    what: "Distribution of the CE-optimal equity share across path bootstraps, plus the optimum under each generator and parameter refit.", x: "Equity share", y: "Count / source", units: "%",
    series: "Histogram + forest.", calc: "Arg-max over the equity grid per resample, generator and refitted history.", read: "Report the range, never a single point.",
    why: "Avoids unsupported precision.", hyp: ["H12"], method: ["ci", "scenarios"], data: OP, related: ["OV-01"] }, ["mc", "study"]),
  v("OP-05", "optimize", "surfaces", "Funding-ratio policy surface", {
    q: "How should equity exposure depend on funding ratio and horizon?",
    what: "CE-optimal equity share (and its success) by funded ratio (wealth / PV of real spending) and horizon.", x: "Funded ratio", y: "Horizon", c: "Equity share / success", units: "%",
    series: "Two heatmaps.", calc: "Wealth set to FR × PV on the TIPS curve; equity grid search.", read: "Underfunded investors may need more risk to have any chance, or less to avoid ruin — the surface shows which.",
    why: "Funding status is a key state variable.", method: ["fi", "utility"], data: OP, related: ["LC-05", "FI-10"] }, ["mc", "curve", "study"]),
  v("OP-06", "optimize", "dynamic", "Static vs parametric vs grid-DP (holdout)", {
    kind: "table", q: "Do richer policy classes beat a static mix out of sample?",
    what: "Train and test CE of static, fitted glidepath and regime-conditional policies, the non-tradable oracle bound and a pointer to grid-DP runs.",
    other: "Table", units: "real $/yr", series: "One row per policy class.", calc: "Selection on training paths, evaluation on disjoint test paths.",
    read: "A large train–test gap is overfitting; the oracle row is an upper bound, not a strategy.", why: "H8: does conditioning help out of sample?", hyp: ["H8"], method: ["dp", "posterior"], data: OP }, ["mc", "regime", "study"]),
  v("OP-07", "optimize", "overview", "Objective switch", {
    kind: "panel", q: "How does the chosen allocation change with the objective?",
    what: "Equity share, CE, success and CVaR under: max CE, max success, min shortfall CVaR, minimax regret across generators, and max CE subject to the success target.",
    other: "KPI cards + success curve", units: "%; real $", series: "One objective at a time.", calc: "Arg-max/min over the equity grid; regret across generators.",
    read: "'Infeasible' means no equity share meets the constraint.", why: "There is no single optimum without an objective.", hyp: ["H9"], method: ["utility"], data: OP, related: ["OP-01"] }, ["mc", "study"]),
  v("OP-08", "optimize", "attribution", "Risk budget & duration constraints", {
    q: "Where does the CE-optimal mix take its risk and duration?",
    what: "Weights vs risk contributions, ex-ante volatility, portfolio duration and liquidity in months of spending.", x: "Sleeve", y: "Share", units: "%; years; months",
    series: "Weight and risk-contribution bars.", calc: "w_i(Σw)_i / w′Σw; durations from the latest GSW curve.", read: "A small weight with a large risk share signals concentration.",
    why: "Implementability needs budgets, not just weights.", method: ["duration"], data: OP }, ["curve", "study"]),
  v("OP-09", "optimize", "robustness", "Parameter stability (tornado)", {
    q: "Which assumptions move the CE-optimal equity share most?",
    what: "Change in the optimal equity share when γ, β, the withdrawal rate or the sample window move to low/high values.", x: "Equity share − baseline", y: "Parameter", units: "pp",
    series: "Low and high bars.", calc: "Re-optimisation under each alternative.", read: "Long bars mean the answer depends on that assumption.", why: "Prioritises what to stress.", method: ["utility"], data: OP }, ["mc", "study"]),
  v("OP-10", "optimize", "robustness", "Optimisation trace", {
    q: "Did the optimiser converge?",
    what: "SLSQP objective evaluations (including finite-difference calls) and the convergence message, verbatim.", x: "Evaluation", y: "CE", units: "real $/yr",
    series: "Objective path.", calc: "scipy SLSQP on static sleeve weights over training paths.", read: "Non-convergence is reported, never hidden.", why: "Trustworthy optima need diagnostics.",
    method: ["utility"], data: OP }, ["study"]),
  v("OP-11", "optimize", "attribution", "Shapley utility by regime (sweep attribution)", {
    q: "Which sleeves add utility to a base equity/Treasury portfolio, unconditionally and by regime?",
    what: "Shapley ΔCE ($/yr) of each added sleeve for the investor of a chosen CE sweep, unconditional and by starting regime.", x: "Sleeve", y: "Shapley MU", units: "real $/yr",
    series: "Bars per condition.", calc: "Exact Shapley over 2^k sleeve subsets, each a fitted static CRRA mix (target-weight kernel).",
    read: "Positive bars add utility; differences across regimes indicate state dependence.", why: "H3/H4 in the original attribution framework.", hyp: ["H3-v2", "H4-v2"],
    method: ["utility"], data: "A completed CE sweep and its attribution run (modern universe).", related: ["OP-03", "OP-12"] }, ["legacy", "mc", "crra"]),
  v("OP-12", "optimize", "attribution", "Marginal utility of one added sleeve", {
    kind: "table", q: "What does adding one sleeve to the base portfolio do to CE?",
    what: "MU_k = CE*(A ∪ {k}) − CE*(A) in % with paired SE, per condition, and base → full CE.", other: "Table", units: "% of CE; real $",
    series: "Rows = conditions; columns = sleeves.", calc: "Paired comparisons of fitted static CRRA mixes.", read: "Compare with the Shapley values: marginal effects depend on the base.",
    why: "Complements OP-11.", hyp: ["H4-v2"], method: ["utility", "ci"], data: "Attribution run.", related: ["OP-11"] }, ["legacy", "mc"]),
  v("OP-13", "optimize", "policy-family", "Policy family ΔCE vs 60/40", {
    q: "Which policy class adds the most CE over 60/40 for the current investor?",
    what: "Paired ΔCE vs 60/40 with ±2 SE whiskers for 60/40, target-date, best constant, fitted glidepath, risk parity, mean–CVaR, static CRRA, regime-dependent, liability bucket and parametric policies. Click a bar for the policy's full results.",
    x: "Policy", y: "ΔCE vs 60/40", units: "%", series: "Blue = gain, red = loss.", calc: "Policies fitted on seed-set A, reported on seed-set B, on the benchmark's paths.",
    read: "Whiskers crossing zero mean the gain is within Monte Carlo noise.", why: "The original optimiser comparison.", hyp: ["H2-v2"], method: ["utility", "dp"], data: "Experiment runs built from the research context.", related: ["OP-14"] }, ["legacy", "mc", "crra"]),
  v("OP-14", "optimize", "policy-family", "Optimal growth-asset share by age", {
    q: "How does each optimised policy's growth share evolve with age?",
    what: "Mean start-of-year growth-asset share by age for each policy in the family.", x: "Age", y: "Growth share", units: "%", series: "One line per policy (fixed colours).",
    calc: "Mean across paths.", read: "Flat lines are static mixes; slopes are glidepaths; kinks reflect regime or funding rules.", why: "Shows what each optimiser does.",
    method: ["dp"], data: "Policy-family experiment runs.", related: ["OP-13", "EX-03"] }, ["legacy"]),
  v("OP-15", "optimize", "dynamic", "DP optimal equity weight (age × cash-on-hand)", {
    q: "In the reduced dynamic program, how does the optimal equity weight depend on age and cash-on-hand?",
    what: "Heatmap of the DP equity weight over age and normalised cash-on-hand for a chosen regime.", x: "Cash-on-hand / permanent income (log)", y: "Age", c: "Equity weight", units: "%",
    series: "Select the regime.", calc: "Backward induction on the reduced 3-asset problem with Markov regimes.", read: "Higher equity at low cash-on-hand reflects human capital acting as a bond.",
    why: "Ground truth for the parametric approximations.", hyp: ["H1-v2"], method: ["dp"], data: "A grid-DP experiment (Markov-switching generator).", related: ["OP-16", "EX-05"],
    lim: ["Reduced annual problem; gains are in-model."] }, ["legacy", "regime"]),
  v("OP-16", "optimize", "dynamic", "DP lifecycle transition: equity vs q", {
    q: "How does the DP's optimal equity weight respond to the signed net-flow rate at fixed ages?",
    what: "Optimal equity weight against q = (c − y)/x for several ages.", x: "q", y: "Equity weight", units: "%", series: "One line per age.",
    calc: "DP policy evaluated on its grid and mapped to q.", read: "A slope at fixed age is the DP's version of the H1 effect.", why: "Headline exhibit of the original lifecycle question.",
    hyp: ["H1-v2"], method: ["dp"], data: "Grid-DP experiment.", related: ["LC-03"] }, ["legacy", "regime"]),
  v("OP-17", "optimize", "dynamic", "DP weight path", {
    q: "Which assets does the DP hold along simulated lives?",
    what: "Mean DP portfolio weights by age along simulated paths.", x: "Age", y: "Weight", units: "%", series: "Stacked by asset.", calc: "DP policy simulated forward.",
    read: "Compare with the target-date glidepath.", why: "Shows the DP policy in use.", method: ["dp"], data: "Grid-DP experiment.", related: ["EX-03"] }, ["legacy"]),
];
