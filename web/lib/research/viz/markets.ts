import { v, type VizEntry } from "./define";

const YC = "GSW nominal/real zero curves from the public panel (/v1/market/yield-curve, /v1/fixed-income/*).";
const MSD = "Public panel with publication lags (/v1/market-state/*).";
const SCN = "Scenario diagnostics study (scenario_lab) on the duration universe.";
const HIST = "Observed universe history (/v1/market/*), selected universe.";

export const MARKETS: VizEntry[] = [
  // ------------------------------------------------------------------ Fixed Income
  v("FI-01", "fixedIncome", "curves", "Nominal / real Treasury yield curves", {
    q: "What do the nominal and real Treasury curves look like at a given month, and how have they moved over a year?",
    what: "GSW zero and derived par curves at the selected month-end, the nominal zero curve one year earlier, and the TIPS real zero curve.",
    x: "Maturity (years)", y: "Yield", units: "% per year (continuously compounded zero; semi-annual par)", series: "Solid = current zero; dashed = par; dotted = one year earlier; separate line = TIPS real.",
    calc: "Read from the GSW fitted curves; par yields derived from zero discount factors.", tex: String.raw`y^{\text{par}}_m=\frac{2(1-d_m)}{\sum_{k} d_{k/2}}`,
    read: "An upward slope is the usual term premium; inversion often precedes slowdowns. Nominal minus real ≈ breakeven inflation plus risk premia.",
    why: "Curves set bond returns, liability values and the cost of defeasing withdrawals.", method: ["fi", "duration"], data: YC, related: ["FI-02", "MS-02"] }, ["curve"]),
  v("FI-02", "fixedIncome", "curves", "Yield-curve evolution", {
    q: "How have 2/5/10/30-year yields evolved through time?",
    what: "Heatmap (or line view) of 2/5/10/30Y GSW zero yields over the history; the line view preserves the original yield-history chart.",
    x: "Month", y: "Tenor (heatmap) or yield (lines)", c: "Yield", units: "% per year", series: "Toggle heatmap / lines.", calc: "Month-end GSW zeros, sampled quarterly in the heatmap.",
    read: "Vertical bands are rate regimes; diverging colours across tenors are slope changes.", why: "Bond outcomes depend on the rate regime a retiree lives through.",
    method: ["fi"], data: YC, related: ["FI-01"] }, ["curve"]),
  v("FI-03", "fixedIncome", "risk", "Duration / DV01 / convexity table", {
    kind: "table", q: "How sensitive is each Treasury par bond to a yield change?",
    what: "Par yield, Macaulay and modified duration, effective duration, convexity and DV01 for Treasury par bonds on the selected curve, plus a shock-preset P&L estimate.",
    other: "Table", units: "years; DV01 in $ per $1m per bp (and per 100 face)", series: "One row per maturity.", calc: "Analytical par-bond formulas; effective duration from a ±1bp parallel bump.",
    tex: String.raw`D_{\text{mod}}=\frac{D_{\text{mac}}}{1+y/2},\quad \text{DV01}=D_{\text{mod}}P\cdot 10^{-4}`, read: "Duration ≈ % price change per 1pp yield move; DV01 is the dollar version.",
    why: "Rate risk is the dominant risk of the defensive sleeve.", method: ["duration"], data: YC, related: ["FI-04", "FI-05"] }, ["curve"]),
  v("FI-04", "fixedIncome", "risk", "Key-rate duration bars", {
    q: "Where on the curve is a bond ladder's rate risk, and does it match the liability?",
    what: "Key-rate durations at 2/5/10/20/30y for an illustrative ladder and for a level withdrawal liability, and their gap.",
    x: "Key rate", y: "Key-rate duration", units: "years", series: "Portfolio, liability, gap.", calc: "Triangular 1bp bumps at each key tenor; they sum to a parallel bump.",
    read: "A gap of zero at every key rate means the ladder hedges the liability against curve shifts.", why: "Liability matching needs more than total duration.",
    method: ["duration", "fi"], data: YC, related: ["FI-10"] }, ["curve"]),
  v("FI-05", "fixedIncome", "risk", "Full repricing vs Taylor approximation", {
    q: "How accurate is the duration–convexity approximation for large rate shocks?",
    what: "Approximation error (bp of price) of duration + convexity vs full repricing for parallel shocks, by maturity; a second view shows the original full-vs-approx P&L bars.",
    x: "Parallel shock (bp)", y: "Error (bp) or P&L (%)", units: "bp; %", series: "Lines per maturity; bars = full repricing, diamonds = approximation.",
    calc: "Full repricing on the shifted zero curve vs −D·Δy + ½·C·Δy².", read: "Errors grow with shock size and maturity; convexity makes long bonds gain more than they lose.",
    why: "Stress tests must use full repricing for large moves.", method: ["duration"], data: YC, related: ["FI-03"] }, ["curve"]),
  v("FI-06", "fixedIncome", "risk", "Bear steepener / bull flattener grid", {
    q: "How does a 10-year bond respond to independent short- and long-end moves?",
    what: "10Y price change for combinations of short-end and long-end yield moves (pivot at 5y), nominal and TIPS.", x: "Long-end move (bp)", y: "Short-end move (bp)", c: "Price change", units: "%",
    series: "Two grids.", calc: "Full repricing with a linear twist of the zero curve.", read: "Bottom-right (short down, long up) is a bear steepener.", why: "Non-parallel moves matter for ladders.",
    method: ["duration"], data: YC, related: ["FI-05"] }, ["curve"]),
  v("FI-07", "fixedIncome", "returns", "Bond return decomposition", {
    q: "Where did the 10-year bond's return come from?",
    what: "Monthly 10Y par-bond return split into carry, roll-down, yield change and convexity, with the residual disclosed; the time-series view shows the last 60 months.",
    x: "Component or month", y: "Monthly return", units: "%", series: "Waterfall (latest month) and stacked bars (history).",
    calc: "carry = y₀Δt; roll = price change on an unchanged curve; yield effect = −D·Δy; convexity = ½CΔy².", read: "A large residual signals curve-shape effects not captured by the decomposition.",
    why: "Separates income from capital gains.", method: ["fi"], data: YC, related: ["FI-02"] }, ["curve"]),
  v("FI-08", "fixedIncome", "curves", "Treasury curve factor PCA", {
    q: "What are the main ways the curve moves?",
    what: "Loadings of the first three principal components of monthly yield changes, with explained variance and the training window.",
    x: "Maturity", y: "Loading", units: "unitless", series: "One line per factor; labels only if loadings pass shape checks.", calc: "Eigendecomposition of the covariance of monthly changes (1–30y).",
    read: "A flat first factor is 'level'; a monotone second is 'slope'.", why: "Factor structure underlies the curve-factor scenario generator.", method: ["fi", "scenarios"], data: YC }, ["curve"]),
  v("FI-09", "fixedIncome", "credit", "Credit spread & default stress", {
    q: "How wide are corporate spreads relative to history?",
    what: "Moody's Baa−Aaa and Baa−10Y Treasury spreads from FRED.", x: "Month", y: "Spread", units: "% per year", series: "Two lines.", calc: "Differences of published yields.",
    read: "Spikes mark credit stress (e.g. 2008, 2020).", why: "Credit sleeves add spread but co-move with equity in crises.", method: ["data"], data: "FRED AAA/BAA/GS10 (public).", related: ["MS-09"],
    lim: ["Spreads are not corporate bond total returns."] }, ["macro"]),
  v("FI-10", "fixedIncome", "liabilities", "Real liability PV and duration gap", {
    q: "What does a stream of real withdrawals cost today, and how sensitive is it?",
    what: "PV and duration of future net withdrawals on the TIPS real curve, the funding ratio of $1m, and sensitivities to mortality, pension, real rates and inflation.",
    x: "PV", y: "Scenario", units: "real US$; years", series: "Bars per sensitivity.", calc: "PV = Σ (W − pension)·S_t·e^{−z_t t}.", read: "A funding ratio below 1 means $1m cannot defease the stream.",
    why: "Liabilities, not benchmarks, define a retiree's risk.", method: ["fi"], data: YC, related: ["FI-11", "LC-05"] }, ["curve"]),
  v("FI-11", "fixedIncome", "liabilities", "Cash-flow matching ladder", {
    q: "How many years of spending can a budget defease with real zero-coupon bonds?",
    what: "Cost of a real zero-coupon rung for each year's withdrawal, with unfunded years highlighted against the budget.", x: "Year", y: "Rung cost", units: "real US$",
    series: "Blue = funded; red = unfunded.", calc: "Rung cost = W·e^{−z_t t} on the real curve.", read: "The first red bar is where the budget runs out.", why: "Ladders are the safest decumulation benchmark.",
    method: ["fi"], data: YC, lim: ["Illustrative pricing, not executable quotes."] }, ["curve"]),
  v("FI-12", "fixedIncome", "returns", "Bond value across the withdrawal spectrum", {
    q: "Which bond instrument raises survival most, and at which withdrawal rates?",
    what: "Change in success (and ΔCE) from moving 40% of an all-equity portfolio into each instrument, across withdrawal rates, paired on the same paths.",
    x: "Withdrawal rate", y: "Δ success (or instrument)", c: "ΔCE", units: "pp; %", series: "Lines/rows per instrument.", calc: "From the bond-frontier study.",
    read: "Positive values mean the instrument helps survival; compare bills with longer bonds.", why: "Duration matters beyond bond share (H7).", hyp: ["H7"], method: ["necessity"],
    data: "Bond-frontier study.", related: ["PP-07", "WL-02"] }, ["mc", "ledger", "pub", "study"]),
  v("FI-13", "fixedIncome", "credit", "Stock–bond co-loss panel", {
    q: "How often do bonds lose when equities crash, and what does that do to survival?",
    what: "Rolling 60m correlation and conditional co-loss frequency (bond loss given equity's worst 20% months), plus 60/40 survival in high vs low co-loss periods.",
    x: "Month", y: "Correlation / probability", units: "unitless; %", series: "Two lines + KPI cards.", calc: "Rolling statistics; bootstrap of high vs low co-loss months.",
    read: "High co-loss periods (like 2022) weaken bonds' hedge.", why: "H10: co-loss explains bond value.", hyp: ["H10"], method: ["scenarios"], data: HIST,
    lim: ["Ex-post classification is descriptive, not a tradable signal."] }, ["hist", "pub"]),
  v("FI-14", "fixedIncome", "credit", "Credit quality / duration surface", {
    kind: "table", q: "How do investment-grade and high-yield outcomes depend on duration and spread?",
    what: "Requires bond-level WRDS data; until then, index-level credit sleeve statistics are shown.", other: "Table", units: "%", series: "Index sleeves.", calc: "Descriptive statistics.",
    read: "Without bond-level data no duration × quality surface is claimed.", why: "Credit is not a safe asset.", method: ["data"], data: "WRDS Bond Returns / TRACE / FISD (not ingested in public mode)." }, ["pub"]),

  // ------------------------------------------------------------------ Market State
  v("MS-01", "marketState", "snapshot", "As-of market state ribbon", {
    kind: "panel", q: "How current is each data source?",
    what: "Latest observation, retrieval vintage, staleness and licence per source, with a backend refresh job.", other: "Source cards", units: "dates; days", series: "One card per source.",
    calc: "Catalog last_obs/vintage vs today; staleness threshold per expected cadence.", read: "'not ingested' and '▲ stale' are honest states, not errors.", why: "No stale data should look current.",
    method: ["data"], data: MSD }, ["registry", "macro"]),
  v("MS-02", "marketState", "snapshot", "Nominal vs real curve (as-of)", {
    q: "What did the curves look like at the as-of date?",
    what: "GSW nominal zero/par and real zero curves available at the as-of date, plus Treasury daily par curves when ingested.", x: "Maturity", y: "Yield", units: "% per year",
    series: "Basis toggle zero/par.", calc: "Point-in-time: only rows published by the as-of date.", read: "As FI-01, dated by availability.", why: "Separates current information from history.",
    method: ["fi"], data: MSD, related: ["FI-01"] }, ["curve"]),
  v("MS-03", "marketState", "snapshot", "Inflation / term-premium decomposition", {
    q: "What do markets and models say about inflation compensation and term premia?",
    what: "10Y nominal CMT, TIPS real yield and breakeven, and the ACM term premium and expected short rate.", x: "Month", y: "Yield", units: "% per year",
    series: "Five series; KPI cards for latest values.", calc: "Published series; breakeven = nominal − real.", read: "ACM components and market breakeven are different decompositions and are not additive across methods.",
    why: "Inflation and term premia drive real bond returns.", method: ["fi"], data: MSD }, ["macro"]),
  v("MS-04", "marketState", "snapshot", "Bond valuation dashboard", {
    kind: "panel", q: "How attractive are bonds at the as-of date?",
    what: "10Y duration, real yield, 2s10s and 5s30s slopes, 1-month roll-down, income per $1m and real ladder income.", other: "KPI cards", units: "years; %; real $",
    series: "Point estimates with stated assumptions.", calc: "From the GSW curve at the as-of date.", read: "Inputs and assumptions are listed in the info; these are not forecasts.",
    why: "Current yields set what a defensive sleeve can deliver.", method: ["duration"], data: MSD }, ["curve"]),
  v("MS-05", "marketState", "dependence", "Rolling stock–bond correlation", {
    q: "Is the stock–bond hedge currently working?",
    what: "12/36/60-month rolling correlations with Fisher-z 95% bands and the DCC-GARCH correlation.", x: "Month", y: "Correlation", units: "−1 to 1",
    series: "One line per window; band on 36m.", calc: "Pearson on rolling windows; DCC(1,1).", read: "Positive correlation means bonds did not hedge equity.", why: "Bond value depends on dependence (H3, H10).",
    hyp: ["H3-v2", "H10"], method: ["scenarios"], data: MSD, related: ["SC-17"] }, ["hist", "pub"]),
  v("MS-06", "marketState", "dependence", "Filtered regime probabilities", {
    q: "What regime does the model think we are in, using only past data?",
    what: "Filtered Markov-switching probabilities through the as-of date, latest and next-month probabilities, and model vintage.", x: "Month", y: "Probability", units: "%",
    series: "One line per regime.", calc: "Hamilton filter (not smoother).", read: "Probabilities near 50% mean the state is uncertain.", why: "Conditioning signals must be point-in-time.",
    hyp: ["H8"], method: ["posterior"], data: MSD, related: ["SC-22"] }, ["regime"]),
  v("MS-07", "marketState", "conditional", "Current-condition scenario fan", {
    q: "How does starting from today's filtered state change projected outcomes?",
    what: "60/40 real wealth fans started from the filtered state at the as-of date vs the stationary distribution, same calibration and seeds.", x: "Years ahead", y: "Real wealth",
    units: "real US$", series: "Two fans; success KPIs.", calc: "Markov-switching paths with different initial state distributions.", read: "Distributions, not point forecasts.",
    why: "Separates state information from unconditional risk.", hyp: ["H8"], method: ["posterior", "scenarios"], data: "As-of study (asof).", related: ["MS-10"] }, ["mc", "regime", "study"]),
  v("MS-08", "marketState", "releases", "Economic release timeline", {
    kind: "table", q: "When was each series published, and what was known at a given date?",
    what: "Last period, availability date, publication lag, vintage and revision notes per series, with a point-in-time selector.", other: "Table + selector", units: "dates; days",
    series: "One row per series.", calc: "available_from = period end + publication lag.", read: "Signals may only use rows available at decision time.", why: "Prevents look-ahead.",
    method: ["data"], data: MSD }, ["macro"]),
  v("MS-09", "marketState", "releases", "Credit spread and liquidity conditions", {
    q: "Where are credit spreads at the as-of date?", what: "Baa−Aaa and Baa−10Y spreads up to the as-of date.", x: "Month", y: "Spread", units: "% per year", series: "Two lines.",
    calc: "Published Moody's yields.", read: "Widening spreads accompany equity stress.", why: "Liquidity and credit stress affect funding.", method: ["data"], data: MSD, related: ["FI-09"] }, ["macro"]),
  v("MS-10", "marketState", "conditional", "Scenario delta board", {
    q: "Does the observed starting state change which allocations meet the success target?",
    what: "Change in success over withdrawal × bond share when starting from the observed state; crosses = within 2 MC SE; table compares b_min.", x: "Withdrawal rate", y: "Bond share",
    c: "Δ P(success)", units: "pp", series: "Heatmap + table.", calc: "Difference of two survival surfaces on matched seeds.", read: "Cells without crosses are state effects beyond noise.",
    why: "Links market state to the bond-necessity question.", hyp: ["H8"], method: ["necessity"], data: "As-of study.", related: ["WL-02"] }, ["mc", "regime", "study"]),
  v("MS-11", "marketState", "releases", "ETF proxy panel", {
    kind: "table", q: "Which WRDS ETF proxy returns are available?", what: "WRDS-sourced ETF series and their last observation, or why none are available.", other: "Table", units: "dates",
    series: "One row per series.", calc: "Catalog lookup.", read: "Empty in public mode.", why: "Implementable portfolios need observed fund returns.", method: ["data"], data: "WRDS CRSP ETFs (authorised host only)." }, ["registry"]),
  v("MS-12", "marketState", "releases", "Refresh audit", {
    kind: "table", q: "What was refreshed, when, and what failed?", what: "Panel builds and Treasury daily refresh attempts with status, plus vintages and series with gaps.", other: "Table", units: "timestamps",
    series: "One row per event.", calc: "Read from ingest audit and refresh logs.", read: "Failures are listed, never hidden.", why: "Data governance.", method: ["data"], data: MSD }, ["registry"]),

  // ------------------------------------------------------------------ Scenarios (study)
  v("SC-01", "scenarios", "generators", "Generator comparison table", {
    kind: "table", q: "Does each scenario generator reproduce the historical data?",
    what: "Per generator: training window, paths, simulated vs historical equity moments, tail quantile, equity–bond correlation, volatility clustering, clipping and a pass/caution/fail verdict.",
    other: "Table", units: "% p.a.; correlations", series: "One row per generator.", calc: "Checks: mean within 2 SE, vol ±15%, q01 within 3pp, correlation ±0.15, clipping < 0.1%.",
    read: "A failing generator should not be the basis of a conclusion.", why: "Model credibility comes before results.", method: ["scenarios"], data: SCN, related: ["SC-12"] }, ["mc", "study"]),
  v("SC-02", "scenarios", "generators", "Simulated vs historical distribution", {
    q: "Do simulated monthly returns match the historical distribution?", what: "Q–Q plot or histogram of simulated vs historical monthly real returns for a chosen asset and generator.",
    x: "Historical quantile / return", y: "Simulated quantile / density", units: "% per month", series: "Diagonal = perfect fit.", calc: "50 quantiles; 40-bin histograms.",
    read: "Departures in the tails matter most for shortfall.", why: "Tail fit drives failure probabilities.", method: ["scenarios"], data: SCN }, ["mc", "study"]),
  v("SC-03", "scenarios", "generators", "Path fan & scenario explorer", {
    q: "How do outcomes differ across generators?", what: "60/40 wealth fan at a 4% draw and sample paths under the chosen generator.", x: "Years", y: "Real wealth", units: "real US$",
    series: "Fan + 12 sample paths.", calc: "Ledger simulation per generator.", read: "Compare success across generators (cards below).", why: "Shows model risk in outcomes.", method: ["scenarios"], data: SCN }, ["mc", "ledger", "study"]),
  v("SC-04", "scenarios", "dependence", "Joint-downside heatmap", {
    q: "How often do stocks and bonds fall together over 12 months — historically, in the model and out of sample?",
    what: "Frequency of 12-month equity loss ≤ x and bond return ≤ y: observed (full and halves), modelled, and a model fitted on the first half.", x: "Bond threshold", y: "Equity threshold",
    c: "Frequency", units: "%", series: "Four small heatmaps.", calc: "Overlapping 12-month windows.", read: "If the model under-states joint losses, it over-states bonds' hedge.",
    why: "Joint downside is what hurts retirees.", hyp: ["H10"], method: ["scenarios"], data: SCN }, ["mc", "hist", "study"]),
  v("SC-05", "scenarios", "dependence", "Rolling and DCC correlation (study)", {
    q: "How has equity–bond correlation changed, and where are the breaks?", what: "36m rolling and DCC correlation on the study universe with PELT change points.", x: "Month", y: "Correlation",
    units: "−1 to 1", series: "Two lines; dotted = change points.", calc: "As SC-17, fixed pair.", read: "Breaks mark regime shifts in dependence.", why: "Dependence is not constant.", method: ["scenarios"], data: SCN, related: ["SC-17"] }, ["hist", "pub", "study"]),
  v("SC-06", "scenarios", "regimes", "Markov state transition matrix (study)", {
    q: "How persistent are regimes and how certain is the state?", what: "Estimated transition matrix, dwell times, stationary probabilities and regime means/vols, with state-uncertainty statistics.",
    x: "To state", y: "From state", c: "Transition probability", units: "probability", series: "Matrix + table.", calc: "EM-estimated Gaussian HMM.", read: "Diagonal near 1 = persistent regimes.",
    why: "Persistence determines regime-switching scenario dynamics.", method: ["posterior"], data: SCN, related: ["SC-24"] }, ["regime", "study"]),
  v("SC-07", "scenarios", "dependence", "Copula tail dependence / exceedance (study)", {
    kind: "table", q: "Do stocks and bonds crash together more than independence implies?", what: "Joint tail exceedances vs the independence expectation at 5% and 10%, and the t-copula fit.",
    other: "Table", units: "counts", series: "Rows per tail level.", calc: "Empirical counts; t-copula by ML.", read: "More joint exceedances than expected means tail dependence.", why: "Tail dependence breaks diversification.",
    method: ["scenarios"], data: SCN, related: ["SC-20"] }, ["hist", "study"]),
  v("SC-08", "scenarios", "stress", "Inflation–rate–return scatter", {
    q: "How do inflation and yield changes relate to bond returns year by year?", what: "Annual CPI inflation vs the change in 10Y yield; hover shows the bond return and year.", x: "CPI inflation (12m)",
    y: "Δ 10Y yield (12m)", units: "%; pp", series: "One point per year.", calc: "Non-overlapping 12-month windows.", read: "Upper-right years (high inflation, rising yields) are worst for nominal bonds.",
    why: "Inflation is the nominal bond's main enemy.", method: ["fi"], data: SCN }, ["hist", "macro", "study"]),
  v("SC-09", "scenarios", "stress", "Stress scenario matrix", {
    q: "How much does each synthetic stress raise failure probability for each portfolio?", what: "Increase in failure probability (and ΔCE) vs matched unstressed paths for six model-generated shocks × five portfolios.",
    x: "Portfolio", y: "Stress", c: "Δ P(failure) / ΔCE", units: "pp; %", series: "Two heatmaps.", calc: "Additive shocks over 12–24 months on bootstrap paths; bonds via −D·Δy.",
    read: "Compare rows to see which portfolio is fragile to which shock.", why: "Stress tests complement probabilistic results.", method: ["scenarios", "duration"], data: SCN }, ["synthetic", "ledger", "study"]),
  v("SC-10", "scenarios", "stress", "Retirement shock timing", {
    q: "Does the timing of a crash matter for the same total loss?", what: "The same −35% equity shock applied in year 0, 5, 10 or 20: median wealth paths and success.", x: "Years since retirement",
    y: "Median real wealth; success", units: "real US$; %", series: "One line per timing.", calc: "Shock applied to matched bootstrap paths.", read: "Early shocks hurt most: sequence risk isolated.",
    why: "Sequence risk is why bonds matter near retirement.", hyp: ["H11"], method: ["shortfall"], data: SCN }, ["synthetic", "ledger", "study"]),
  v("SC-11", "scenarios", "generators", "Historical cohort start-date map", {
    q: "What actually happened to each historical retirement cohort?", what: "Success/failure and terminal real wealth by actual cohort start for several portfolios.", x: "Cohort start",
    y: "Portfolio / terminal wealth", units: "indicator; real US$", series: "Heatmap + lines.", calc: "Historical generator with a 30-year horizon.", read: "Failures cluster in specific start eras (sequence risk).",
    why: "The historical record is the benchmark for every model.", method: ["scenarios"], data: SCN }, ["hist", "ledger", "pub", "study"]),
  v("SC-12", "scenarios", "diagnostics", "Model mismatch diagnostics", {
    q: "Are historical returns consistent with each generator's simulated marginal distribution?", what: "PIT histograms of historical returns under each generator's simulated marginal, with χ² tests and red flags; QLIKE comparison.",
    x: "PIT decile", y: "Count", units: "counts", series: "Bars per asset; ⚑ = p < 0.01.", calc: "PIT = empirical CDF of simulated returns at each historical return.",
    read: "A flat histogram means good calibration; U or hump shapes mean wrong tails or spread.", why: "Calibration diagnostics prevent false confidence.", method: ["scenarios"], data: SCN, related: ["SC-01"] }, ["mc", "study"]),

  // ------------------------------------------------------------------ Scenarios (historical analytics; original Research Lab)
  v("SC-13", "scenarios", "historical-analytics", "Return moments", {
    kind: "table", q: "What were the historical return, risk and shape of each sleeve?",
    what: "Annualised nominal and real mean, geometric real return, volatility, skewness, kurtosis, maximum real drawdown and Sharpe ratio for each asset in the selected universe.",
    other: "Table", units: "% p.a.; unitless", series: "One row per sleeve; excluded optional sleeves listed below.", calc: "Monthly returns annualised (×12, ×√12); real = (1+R)/(1+π) − 1.",
    tex: String.raw`R^{\text{real}}_t=\frac{1+R_t}{1+\pi_t}-1`, read: "Kurtosis above 3 means fat tails; Sharpe uses T-bills as the risk-free rate.", why: "The starting point for every scenario model.",
    method: ["data"], data: HIST, related: ["SC-14"] }, ["hist", "pub"]),
  v("SC-14", "scenarios", "historical-analytics", "Real drawdowns", {
    q: "How deep and long were real losses for each sleeve?", what: "Peak-to-trough decline of each sleeve's real wealth index.", x: "Month", y: "Drawdown", units: "%", series: "One line per sleeve.",
    calc: "W_t/max_{s≤t}W_s − 1 on the real index.", read: "Long, deep drawdowns are what a retiree must survive while withdrawing.", why: "Drawdown duration matters for sequence risk.", method: ["data"], data: HIST }, ["hist", "pub"]),
  v("SC-15", "scenarios", "historical-analytics", "Rolling 36-month volatility", {
    q: "How has volatility changed over time?", what: "Annualised 36-month rolling volatility of nominal returns per sleeve.", x: "Month", y: "Volatility", units: "% p.a.", series: "One line per sleeve.",
    calc: "Rolling standard deviation × √12.", read: "Volatility clusters; bonds were far more volatile in the 1980s.", why: "Constant-volatility models miss clustering.", method: ["scenarios"], data: HIST }, ["hist", "pub"]),
  v("SC-16", "scenarios", "historical-analytics", "Real-return correlation matrix", {
    q: "How correlated are the sleeves over the full window?", what: "Pairwise correlation of monthly real returns.", x: "Asset", y: "Asset", c: "Correlation", units: "−1 to 1", series: "Symmetric matrix.",
    calc: "Pearson correlation on the full window.", read: "Low or negative equity–bond correlation is what makes bonds diversifiers.", why: "Inputs to every allocation decision.", method: ["scenarios"], data: HIST, related: ["SC-17"] }, ["hist", "pub"]),
  v("SC-17", "scenarios", "dependence", "Rolling correlation for an asset pair", {
    q: "How has the correlation between two chosen assets evolved?", what: "12/36/60-month rolling Pearson correlation and DCC-GARCH(1,1) for the selected pair, with PELT change points.",
    x: "Month", y: "Correlation", units: "−1 to 1", series: "One line per window + DCC; dotted = change points.", calc: "Rolling Pearson; DCC estimated on the full sample; PELT on the standardised cross-product.",
    read: "Sign changes (e.g. after 2000, again in 2022) are regime shifts in the hedge.", why: "Bond value depends on this correlation.", hyp: ["H3-v2", "H10"], method: ["scenarios"], data: HIST, related: ["MS-05"],
    lim: ["DCC parameters are estimated on the full sample; rolling statistics are strictly backward-looking."] }, ["hist", "pub"]),
  v("SC-18", "scenarios", "dependence", "Joint-loss frequency by decade", {
    q: "In which decades did both assets fall together most often?", what: "P(both below their 10% quantile) per decade; the dotted line is the 1% independence benchmark.",
    x: "Decade", y: "Joint-loss frequency", units: "%", series: "Bars per decade.", calc: "Share of months with both returns below their full-sample 10% quantiles.",
    read: "Bars well above 1% mean losses cluster together.", why: "Joint losses defeat diversification.", hyp: ["H10"], method: ["scenarios"], data: HIST }, ["hist", "pub"]),
  v("SC-19", "scenarios", "dependence", "Inflation-regime conditioning", {
    kind: "table", q: "Does the stock–bond relationship differ when inflation is high?", what: "Correlation and joint-loss frequency when YoY CPI is above vs below 3%, with month counts.",
    other: "Table", units: "correlation; %", series: "Two regimes.", calc: "Conditional statistics by inflation regime.", read: "Higher correlation in high inflation means bonds hedge less when inflation bites.",
    why: "Links inflation to bond value (H3).", hyp: ["H3-v2"], method: ["scenarios"], data: HIST }, ["hist", "macro", "pub"]),
  v("SC-20", "scenarios", "dependence", "Student-t copula tails", {
    kind: "panel", q: "How strong is lower-tail dependence between the pair?", what: "t-copula correlation ρ, degrees of freedom ν, implied tail dependence λ and Kendall τ.",
    other: "Parameter cards", units: "unitless", series: "Four parameters.", calc: "ρ from Kendall's τ; ν by profile maximum likelihood.", tex: String.raw`\lambda=2\,t_{\nu+1}\!\left(-\sqrt{\tfrac{(\nu+1)(1-\rho)}{1+\rho}}\right)`,
    read: "λ > 0 means extreme losses co-occur more than a Gaussian implies.", why: "Tail dependence matters for shortfall.", method: ["scenarios"], data: HIST, related: ["SC-07"] }, ["hist", "pub"]),
  v("SC-21", "scenarios", "dependence", "Out-of-sample covariance forecasts", {
    kind: "table", q: "Which covariance model forecasts next-month risk best?", what: "One-month-ahead covariance forecasts scored with QLIKE and realised minimum-variance volatility on unseen months.",
    other: "Table", units: "QLIKE; % p.a.", series: "One row per model.", calc: "Rolling estimation, out-of-sample scoring.", read: "Lower QLIKE is better.", why: "Risk-based rules need good forecasts.", method: ["scenarios"], data: HIST,
    lim: ["DCC parameters are estimated on the full sample; other forecasts are strictly rolling."] }, ["hist", "pub"]),
  v("SC-22", "scenarios", "regimes", "Regime probabilities", {
    q: "When was the market in each regime?", what: "Filtered (decision-grade) or smoothed (descriptive) Markov-switching probabilities over time, with the retrospective NBER recession indicator.",
    x: "Month", y: "Probability", units: "%", series: "Stacked areas per regime; NBER line is retrospective only.", calc: "Hamilton filter / Kim smoother for K = 2 or 3.",
    read: "Filtered probabilities use only past data; smoothed use the whole sample.", why: "Regimes condition bond value and policies.", hyp: ["H3-v2", "H8"], method: ["posterior"], data: HIST, related: ["MS-06"] }, ["regime", "pub"]),
  v("SC-23", "scenarios", "regimes", "Regime means and volatility", {
    kind: "table", q: "What characterises each regime?", what: "Annualised real mean and volatility of each series in each regime.", other: "Table", units: "% p.a.", series: "Rows = series; columns = regimes.",
    calc: "Regime-specific Gaussian parameters.", read: "Labels are assigned after inspecting these estimates.", why: "Gives economic meaning to regimes.", method: ["posterior"], data: HIST }, ["regime", "pub"]),
  v("SC-24", "scenarios", "regimes", "Transition matrix & model selection", {
    kind: "table", q: "How persistent are regimes, and how many should there be?", what: "Transition probabilities, expected durations and BIC for K = 1, 2, 3.", other: "Table", units: "probability; months",
    series: "Rows = from-state.", calc: "EM estimation; E[duration] = 1/(1 − p_ss).", read: "Lower BIC is preferred, subject to interpretability.", why: "Model selection should be explicit.", method: ["posterior"], data: HIST, related: ["SC-06"] }, ["regime", "pub"]),
  v("SC-25", "scenarios", "factors", "Factor exposures", {
    kind: "table", q: "Which systematic factors explain each sleeve's returns?", what: "OLS of monthly excess returns on Fama–French factors (Mkt-RF, SMB, HML, RMW, CMA, UMD) with α, t(α), betas, R² and sample size.",
    other: "Table", units: "α % p.a.; betas unitless", series: "One row per sleeve.", calc: "OLS over each sleeve's overlap with the factor data.", tex: String.raw`R_i-R_f=\alpha+\beta^{\top}F+\varepsilon`,
    read: "A high market beta for credit means it behaves partly like equity.", why: "Distinguishes true diversifiers from disguised equity.", method: ["data"], data: HIST + " Ken French factors." }, ["hist", "pub"]),
];
