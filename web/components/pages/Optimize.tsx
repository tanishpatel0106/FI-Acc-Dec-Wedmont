"use client";
import { useState } from "react";
import { DPPanel, PolicyFamily } from "@/components/research/optimize/PolicyFamily";
import { SweepAttribution } from "@/components/research/compare/SavedRunAnalytics";
import { ResearchPage, Sec } from "@/components/research/page";
import { ContextBar, DataTable, Grid, Kpi, Seg, StudyGate, Viz, Warnings, dataClassOf } from "@/components/research/kit";
import { Bars, Forest, Heat, Histo, Lines, Scatter, pct, spct, usd } from "@/components/visualizations/charts";
import { useStudyLatest } from "@/lib/api/v2";
import { useVizTokens } from "@/components/visualizations/Plot";

/* eslint-disable @typescript-eslint/no-explicit-any */
function Body({ env }: { env: any }) {
  const r = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(r);
  const t = useVizTokens();
  const sf = useStudyLatest("signed_flow");
  const [obj, setObj] = useState(r.objectives[0].objective);
  const sel = r.objectives.find((o: any) => o.objective === obj) ?? r.objectives[0];
  const p = r.pareto as any[];
  const wlab = (w: any) => Object.entries(w).filter(([, v]: any) => v > 0).map(([k, v]: any) => k + " " + pct(v, 0)).join(", ");
  const band = r.uncertainty_band;
  const sfr = sf.data?.status === "done" ? sf.data.results : null;
  return (
    <div className="space-y-4">
      <ContextBar items={[["Universe", r.universe.name], ["Withdrawal", pct(r.withdrawal, 1)], ["Success target", pct(r.target, 0)], ["Paths", r.n_paths], ["Sleeves", r.sleeves.join(", ")], ["Run", runId.slice(0, 10)]]} />
      <Warnings items={r.warnings} />
      <Sec id="overview"><Grid>
        <Viz id="OP-01" title="CE–survival Pareto frontier" question={"Static long-only mixes in (failure probability, CE) space; target constraint P(success) ≥ " + pct(r.target, 0) + " shaded."} runId={runId} cls={cls} block="pareto"
          definition="Each point is one simplex mix on the shared tensor. Pareto = no other mix has both higher CE and lower failure probability. Shaded region violates the success constraint.">
          <Scatter xTitle="P(failure, fixed horizon)" yTitle="CE ($/yr)" xfmt=".0%" yfmt="$,.0f" pts={[
            { name: "dominated", x: p.filter((c) => !c.pareto).map((c) => c.p_fail), y: p.filter((c) => !c.pareto).map((c) => c.ce), text: p.filter((c) => !c.pareto).map((c) => wlab(c.weights)), color: t.text2, size: 7 },
            { name: "Pareto", x: p.filter((c) => c.pareto).map((c) => c.p_fail), y: p.filter((c) => c.pareto).map((c) => c.ce), text: p.filter((c) => c.pareto).map((c) => wlab(c.weights)), size: 11 }]}
            shapes={[{ type: "rect", x0: 1 - r.target, x1: 1, yref: "paper", y0: 0, y1: 1, fillcolor: "rgba(127,127,127,0.12)", line: { width: 0 } }]} />
        </Viz>
        <Viz id="OP-07" title="Objective switch" question="The same grid optimised for CE, fixed-horizon success, shortfall CVaR, robust minimax regret, and CE under the success constraint." runId={runId} cls={cls}>
          <Seg value={obj} onChange={setObj} options={r.objectives.map((o: any) => ({ value: o.objective, label: o.objective }))} />
          <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
            <Kpi label="equity share" value={sel.equity === null ? "infeasible" : pct(sel.equity, 0)} sub={sel.constraint ?? (sel.max_regret !== undefined ? "max regret " + pct(sel.max_regret, 2) : "")} />
            <Kpi label="CE" value={usd(sel.ce)} /><Kpi label="P(success)" value={pct(sel.success)} /><Kpi label="CVaR95 unmet" value={usd(sel.cvar95_unmet)} />
          </div>
          <Lines height={220} xTitle="equity share" yTitle="P(success)" xfmt=".0%" yfmt=".0%" lines={[{ name: "P(success)", x: r.by_equity.map((b: any) => b.equity), y: r.by_equity.map((b: any) => b.success), mode: "lines+markers" }]} />
        </Viz>
      </Grid></Sec>
      <Sec id="surfaces"><Grid>
        <Viz id="OP-02" title="Optimal weight surfaces" question="CE-optimal equity share by withdrawal rate × starting regime (this study) and by q × age (signed-flow study); optimised vs fixed 60%." runId={runId} cls={cls}>
          <Heat height={220} x={r.regime_surface.r} y={r.regime_surface.regimes} z={r.regime_surface.equity} xTitle="withdrawal rate" yTitle="start" zTitle="equity share" xfmt={(v) => pct(v, 0)} zmin={0} zmax={1} />
          {sfr ? <Heat height={240} x={sfr.q} y={sfr.ages} z={sfr.risky_share_ce} xTitle="planned q" yTitle="age" zTitle="risky share" xfmt={(v) => (v * 100).toFixed(1) + "%"} zmin={0} zmax={1} text={false} />
            : <div className="text-xs text-muted-foreground">q × age surface appears once the signed-flow study has run.</div>}
        </Viz>
        <Viz id="OP-05" title="Funding-ratio policy surface" question="CE-optimal equity share by funded ratio (wealth / PV of real spending) and horizon; success at the optimum in the table." runId={runId} cls={cls} definition={r.funding_ratio_surface.constraints}>
          <Heat x={r.funding_ratio_surface.funded_ratios} y={r.funding_ratio_surface.horizons} z={r.funding_ratio_surface.equity} xTitle="funded ratio" yTitle="horizon (years)" zTitle="equity share" zmin={0} zmax={1} />
          <Heat height={220} x={r.funding_ratio_surface.funded_ratios} y={r.funding_ratio_surface.horizons} z={r.funding_ratio_surface.success} xTitle="funded ratio" yTitle="horizon" zTitle="P(success)" zmin={0} zmax={1} />
        </Viz>
      </Grid></Sec>
      <Sec id="attribution"><Grid>
        <Viz id="OP-03" title="Risk / utility contribution" question="Shapley CE contribution of each non-equity sleeve (40% equity base) and the marginal ΔCE of adding 10% to 60/40, with CIs." runId={runId} cls={cls}
          definition="Shapley baseline: 100% equity; coalition S = 40% equity + 60% split equally across S. CIs: path bootstrap (60 resamples). Marginal: paired ΔCE with path-bootstrap CI.">
          <Forest xTitle="Shapley CE ($/yr)" xfmt="$,.0f" rows={r.shapley.map((s: any) => ({ label: s.sleeve, est: s.shapley_ce, lo: s.lo, hi: s.hi }))} />
          <Forest xTitle="ΔCE of +10% sleeve vs 60/40" xfmt="+.2%" rows={r.marginal.map((s: any) => ({ label: "+10% " + s.sleeve, est: s.delta, lo: s.lo, hi: s.hi }))} />
        </Viz>
        <Viz id="OP-08" title="Risk budget & duration constraints" question="Risk contributions, per-sleeve bounds, total duration and liquidity for the CE-optimal simplex mix." runId={runId} cls={cls}>
          <Bars xTitle="sleeve" yTitle="share" yfmt=".0%" x={Object.keys(r.risk_budget.weights)} series={[{ name: "weight", y: Object.values(r.risk_budget.weights) as number[] }, { name: "risk contribution", y: Object.values(r.risk_budget.risk_contribution) as number[] }]} />
          <div className="grid grid-cols-3 gap-2"><Kpi label="ex-ante vol" value={pct(r.risk_budget.vol_annual)} /><Kpi label="portfolio duration" value={r.risk_budget.portfolio_duration.toFixed(2) + "y"} />
            <Kpi label="liquidity" value={r.risk_budget.liquidity_months_of_spending === null ? "–" : r.risk_budget.liquidity_months_of_spending.toFixed(1) + " months"} sub={"bounds " + r.risk_budget.bounds.min + "–" + r.risk_budget.bounds.max} /></div>
        </Viz>
      </Grid></Sec>
      <Sec id="robustness"><Grid>
        <Viz id="OP-04" title="Policy uncertainty band" question="Range of the CE-optimal equity share across path resamples, generators and parameter refits — a range, not an 'optimal 37%' point." runId={runId} cls={cls} definition={band.note}>
          <Histo xTitle="CE-optimal equity share (path bootstrap)" xfmt=".0%" bars={[{ name: "bootstrap", x: [...new Set(band.path_bootstrap.values as number[])].sort(), y: [...new Set(band.path_bootstrap.values as number[])].sort().map((v) => band.path_bootstrap.values.filter((x: number) => x === v).length) }]} />
          <Forest xTitle="equity share" xfmt=".0%" ref={null} rows={[{ label: "path bootstrap (5–95%)", est: band.path_bootstrap.q50, lo: band.path_bootstrap.q05, hi: band.path_bootstrap.q95 },
            ...Object.entries(band.generators).map(([g, v]: any) => ({ label: "generator: " + g, est: typeof v === "number" ? v : null, note: typeof v === "string" ? v : undefined })),
            ...band.parameter_refits.map((v: number, i: number) => ({ label: "parameter refit " + (i + 1), est: v }))]} />
        </Viz>
        <Viz id="OP-09" title="Parameter stability (tornado)" question={"CE-optimal equity share (baseline " + pct(r.base_equity, 0) + ") under low/high values of γ, β, withdrawal rate and sample window."} runId={runId} cls={cls}>
          <Bars horizontal xTitle="parameter" yTitle="equity share − baseline" yfmt="+.0%" x={r.tornado.map((x: any) => x.parameter)} series={[
            { name: "low", y: r.tornado.map((x: any) => x.low - r.base_equity) }, { name: "high", y: r.tornado.map((x: any) => x.high - r.base_equity) }]} />
        </Viz>
        <Viz id="OP-10" title="Optimisation trace" question="SLSQP objective evaluations (including finite-difference calls) and the sum-to-one residual; convergence status reported verbatim." runId={runId} cls={cls}
          definition={"Converged: " + r.optimisation_trace.converged + " — " + r.optimisation_trace.message + ". Solution: " + JSON.stringify(r.optimisation_trace.solution)}>
          <Lines xTitle="evaluation" yTitle="CE ($/yr)" yfmt="$,.0f" lines={[{ name: "objective", x: r.optimisation_trace.evaluations.map((e: any) => e.iteration), y: r.optimisation_trace.evaluations.map((e: any) => e.ce), mode: "lines+markers" }]} />
          <div className={"text-xs " + (r.optimisation_trace.converged ? "text-muted-foreground" : "text-[var(--viz-s8)]")}>{r.optimisation_trace.converged ? "✓ converged" : "⚠ did not converge"}: {r.optimisation_trace.message}</div>
        </Viz>
      </Grid></Sec>
      <Sec id="dynamic"><Grid>
        <Viz id="OP-06" title="Static vs parametric vs grid-DP" question="Holdout CE on disjoint test paths and train/test fit; the oracle (latent-state) policy is shown separately as a non-tradable bound." runId={runId} cls={cls}>
          <DataTable rows={r.policy_classes} columns={[{ key: "policy", label: "policy" }, { key: "selected", label: "parameters", fmt: (v) => (Array.isArray(v) ? v.map((x: number) => x.toFixed(2)).join(", ") : v === undefined ? "–" : Number(v).toFixed(2)) },
            { key: "ce_train", label: "CE train", fmt: usd }, { key: "ce_test", label: "CE test", fmt: usd }, { key: "holdout_regret", label: "holdout regret", fmt: (v) => pct(v, 2) },
            { key: "oracle", label: "oracle?", fmt: (v) => (v ? "YES (not tradable)" : "no") }, { key: "pointer", label: "note" }]} />
        </Viz>
      </Grid></Sec>
      <Sec id="surfaces"><div className="text-xs text-muted-foreground">Regime bond value (H3): {r.regime_surface.bond_marginal.map((row: any[], i: number) => r.regime_surface.regimes[i] + " " + spct(row[Math.floor(row.length / 2)]?.delta)).join(" · ")} (ΔCE of 60/40 vs 100% equity at the middle withdrawal rate).</div></Sec>
    </div>
  );
}

const STUDY_SECTIONS = ["overview", "surfaces", "attribution", "robustness", "dynamic"];

/** Portfolio Optimization: one optimizer workflow — multi-objective study, policy family, DP and attribution. */
export function Optimize() {
  return (
    <ResearchPage page="optimize" intro="CE versus survival versus shortfall: Pareto sets, objective switching, sleeve contributions, uncertainty bands across resamples/generators/refits, funding-ratio surfaces, holdout policy classes, the ten-policy family, grid dynamic programming and the optimiser's own trace.">
      <Sec id={STUDY_SECTIONS}>
        <StudyGate kind="optimize" title="Multi-objective study">{(env) => <Body env={env} />}</StudyGate>
      </Sec>
      <Sec id="attribution"><SweepAttribution /></Sec>
      <Sec id="policy-family"><PolicyFamily /></Sec>
      <Sec id="dynamic">
        <h2 className="mt-6 text-base font-semibold">Grid dynamic programming</h2>
        <DPPanel />
      </Sec>
    </ResearchPage>
  );
}
