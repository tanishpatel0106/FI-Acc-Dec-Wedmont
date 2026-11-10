import { v, type VizEntry } from "./define";

const LS = "Multi-asset lifecycle simulation (lifecycle_sim): a dated investor simulated to the final age with multi-asset, state-dependent policies on the holdings ledger.";
const AS = ["Scenario source 'simulated from start' uses only information published before the start date (no hindsight); 'history then simulated' lives through actual history first, then continues from the exact realised holdings.",
  "Every path recomputes the policy's target every month from its own wealth, human capital, liabilities and trailing signals; trades follow the rebalancing rule with costs on executed notional."];
const LIM = ["Bootstrap of joint real returns and CPI from the information set: the future resembles the sampled history.",
  "Sleeves with less than 15 years of joint history at the information date are excluded from the forward universe (reported).",
  "Public tier: Treasuries, TIPS and IG credit are repriced from yields; gold, commodities and high yield need WRDS and are never proxied."];

export const LIFESIM: VizEntry[] = [
  v("LS-01", "lifecycle", "simulator", "Mean allocation by age (multi-asset)", {
    q: "How does the policy's allocation across asset classes change as the investor ages?",
    what: "Average holding of every sleeve at the start of each year of age across all simulated paths, for the selected policy (and the realised history first, when the scenario source includes it).",
    x: "Age", y: "Average weight", c: "Sleeve", units: "% of portfolio", series: "Stacked areas sum to 100%.",
    calc: "Mean across paths of ledger holdings divided by wealth, each year of age.",
    read: "A flat band means a static policy; a shifting band means the policy reacts to the investor's state or to market signals.",
    why: "It replaces the two-asset, nearly constant weight path of the classic simulator with the full multi-asset allocation.", method: ["rebalancing"], data: LS,
    related: ["LS-02", "EX-03", "HR-12"], as: AS, lim: LIM }, ["mc", "ledger", "study"]),
  v("LS-02", "lifecycle", "simulator", "Allocation dispersion across paths", {
    q: "Do investors of the same age hold the same portfolio under this policy?",
    what: "The 10th–90th percentile range and median of the growth (equity) share by age across paths.",
    x: "Age", y: "Growth share", units: "% of portfolio", series: "Band: 10–90%; line: median.",
    calc: "Quantiles across paths of the summed equity-sleeve weights each year.",
    read: "A wide band means the allocation depends on each path's wealth and signals, not on age alone.",
    why: "State-dependence is visible as dispersion.", method: ["rebalancing"], data: LS, related: ["LS-01"], as: AS, lim: LIM }, ["mc", "ledger", "study"]),
  v("LS-03", "lifecycle", "simulator", "Real wealth fan by age", {
    q: "What range of wealth does the investor reach under each policy?",
    what: "5–95% and 25–75% bands and the median of real wealth by age; the dashed line marks retirement.",
    x: "Age", y: "Real wealth", units: "US$ of the information date", series: "Bands and median for the selected policy; dotted: benchmark median.",
    calc: "Ledger wealth at the start of each year of age across paths.",
    read: "Compare medians and the 5% tail; the tail at and after retirement is what spending depends on.",
    why: "Growth and protection in one view.", method: ["wealth"], data: LS, related: ["LS-04", "EX-01"], as: AS, lim: LIM }, ["mc", "ledger", "study"]),
  v("LS-04", "lifecycle", "simulator", "Policy outcomes", {
    kind: "table", q: "Which policy best funds this investor's lifetime?",
    what: "For every policy: lifetime certainty-equivalent consumption, probability of funding every desired withdrawal to the final age, shortfall severity and wealth at retirement.",
    other: "Sortable table", units: "US$, %", series: "One row per policy, same paths.",
    calc: "Ledger utility of funded consumption (mortality-weighted, γ), first shortfall, unmet spending and wealth at the retirement month.",
    read: "A policy can raise median wealth and still lose on shortfall risk.",
    why: "Puts lifetime welfare and retirement security side by side.", method: ["utility", "shortfall"], data: LS, related: ["LS-03", "HR-13"], as: AS, lim: LIM }, ["mc", "ledger", "crra", "study"]),
  v("LS-05", "lifecycle", "simulator", "Starting allocation and information set", {
    kind: "table", q: "What does each policy hold on day one, and what information was it allowed to use?",
    what: "The first target of each policy, the information date, the eligible and excluded sleeves.",
    other: "Table", units: "% of portfolio", series: "One row per policy.",
    calc: "Policy target at the start state from point-in-time estimates.",
    read: "Sleeves listed as excluded had too little history at the start date; they are not proxied.",
    why: "Makes the no-hindsight claim checkable.", method: ["data"], data: LS, related: ["LS-01", "MA-01"], as: AS, lim: LIM }, ["study"]),
];
