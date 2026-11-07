"use client";
import { useState } from "react";
import { PageHeader } from "@/components/common/Section";
import { ContextBar, DataTable, Grid, GradeTag, Kpi, Seg, StudyGate, Viz, Warnings } from "@/components/v2/kit";
import { Bars, Fan, Heat, Lines, Matrix, Scatter, pct, spct } from "@/components/v2/charts";

/* eslint-disable @typescript-eslint/no-explicit-any */
function Body({ env }: { env: any }) {
  const r = env.results;
  const runId = env.run_id as string;
  const gens = r.generators.filter((g: any) => !g.error).map((g: any) => g.generator);
  const [g, setG] = useState(gens.includes("bootstrap") ? "bootstrap" : gens[0]);
  const [asset, setAsset] = useState(r.distribution.assets[0]);
  const [view, setView] = useState<"hist" | "qq">("qq");
  const [pf, setPf] = useState(Object.keys(r.shock_timing.portfolios)[0]);
  const bins = r.distribution.bins.slice(0, -1).map((b: number, i: number) => (b + r.distribution.bins[i + 1]) / 2);
  const regs = r.regimes;
  const cohortP = r.cohorts.available ? Object.keys(r.cohorts.portfolios) : [];
  return (
    <div className="space-y-4">
      <ContextBar items={[["Universe", r.universe.name], ["Window", r.universe.window.join(" → ")], ["Generators", gens.join(", ")], ["Run", runId.slice(0, 10)]]} />
      <Warnings items={r.warnings} />
      <Viz id="SC-01" title="Generator comparison table" question="Training sample, paths, dependence fit, tails and an automatic diagnostic verdict per generator." runId={runId} cls="model_generated"
        definition="Checks: mean within 2 SE of history, vol within ±15%, 1% monthly equity quantile within 3pp, equity–bond correlation within ±0.15, clipping < 0.1%. Pass = all; caution = ≥3; fail otherwise.">
        <DataTable rows={r.generators.map((x: any) => ({ ...x, mean: x.equity_sim?.mean_annual, vol: x.equity_sim?.vol_annual, q01: x.equity_sim?.q01, hm: x.equity_hist?.mean_annual }))} columns={[
          { key: "generator", label: "generator" }, { key: "training_window", label: "training", fmt: (v) => (v ? v.join("→") : "–") }, { key: "n_paths", label: "paths" },
          { key: "mean", label: "eq mean (sim)", fmt: (v, row) => pct(v) + " vs " + pct(row.hm) }, { key: "vol", label: "eq vol", fmt: (v) => pct(v) }, { key: "q01", label: "eq q01", fmt: (v) => pct(v) },
          { key: "corr_eq_bond_sim", label: "corr sim/hist", fmt: (v, row) => (v === undefined ? "–" : v.toFixed(2) + " / " + row.corr_eq_bond_hist.toFixed(2)) },
          { key: "acf_sq_sim", label: "ACF r² sim/hist", fmt: (v, row) => (v === undefined ? "–" : v.toFixed(2) + " / " + row.acf_sq_hist.toFixed(2)) },
          { key: "clipped_share", label: "clipped", fmt: (v) => pct(v, 3) }, { key: "verdict", label: "verdict", fmt: (v, row) => <span title={row.error}><GradeTag grade={v === "pass" ? "supported" : v === "fail" ? "invalid" : "fragile"} /> {v}</span> }]} />
      </Viz>
      <div className="flex flex-wrap gap-3"><Seg label="Generator" value={g} onChange={setG} options={gens.map((x: string) => ({ value: x, label: x }))} />
        <Seg label="Asset" value={asset} onChange={setAsset} options={r.distribution.assets.map((a: string) => ({ value: a, label: a }))} /></div>
      <Grid>
        <Viz id="SC-02" title="Simulated vs historical distribution" question="Monthly real returns: histogram or Q–Q against the historical sample; clipping share in SC-01." runId={runId} cls="model_generated">
          <Seg value={view} onChange={setView} options={[{ value: "qq", label: "Q–Q" }, { value: "hist", label: "histogram" }]} />
          {view === "qq" ? <Scatter diagonal xTitle="historical quantile" yTitle={g + " quantile"} xfmt=".1%" yfmt=".1%" pts={[{ name: asset, x: r.distribution.hist[asset].quantiles, y: r.distribution.generators[g]?.[asset]?.quantiles ?? [] }]} />
            : <Lines xTitle="monthly real return" yTitle="density" xfmt=".0%" lines={[
              { name: "historical", x: bins, y: (() => { const c = r.distribution.hist[asset].hist_counts; const s = c.reduce((a: number, b: number) => a + b, 0); return c.map((v: number) => v / s); })() },
              { name: g, x: bins, y: (() => { const c = r.distribution.generators[g]?.[asset]?.hist_counts ?? []; const s = c.reduce((a: number, b: number) => a + b, 0) || 1; return c.map((v: number) => v / s); })() }]} />}
        </Viz>
        <Viz id="SC-03" title="Path fan & scenario explorer" question={"60/40 at a 4% real draw: real wealth fan and sample paths under " + g + "."} runId={runId} cls="model_generated">
          {r.fans[g] ? <>
            <Fan x={r.fans[g].wealth.p50.map((_: number, i: number) => i)} q={r.fans[g].wealth} name={g} xTitle="years" yTitle="real wealth" />
            <Lines height={200} legend={false} xTitle="years" yTitle="sample paths" yfmt="$,.0f" lines={r.fans[g].sample_wealth.map((p: number[], i: number) => ({ name: "path " + i, x: p.map((_, k) => k), y: p, width: 1 }))} />
            <div className="text-xs text-muted-foreground">P(30y success) under {g}: {pct(r.fans[g].success)}</div>
          </> : null}
        </Viz>
        <Viz id="SC-04" title="Joint-downside heatmap" question={"Frequency of 12-month equity loss ≤ x AND " + r.joint_downside.bond + " return ≤ y: observed, modelled and out-of-sample."} runId={runId} cls="model_generated"
          definition={"OOS: bootstrap fitted on history up to " + (r.joint_downside.oos_split ?? "–") + ", compared with the observed second half. Overlapping 12-month windows."}>
          {[["observed (full)", r.joint_downside.observed], ["modelled: " + g, r.joint_downside.modeled[g]], ["observed second half", r.joint_downside.observed_second_half], ["model fit on first half (OOS)", r.joint_downside.oos_first_half_model]]
            .filter(([, z]) => z).map(([lab, z]: any) => <div key={lab}><div className="text-[11px] text-muted-foreground">{lab}</div>
              <Heat height={170} x={r.joint_downside.bond_thresholds.map((v: number) => "bond ≤ " + pct(v, 0))} y={r.joint_downside.eq_thresholds.map((v: number) => "eq ≤ " + pct(v, 0))} z={z}
                xTitle="" yTitle="" zTitle="frequency" zfmt=".1%" zmin={0} /></div>)}
        </Viz>
        <Viz id="SC-05" title="Rolling and DCC correlation" question="Equity–bond rolling correlations with detected change points (dated vertical lines)." runId={runId} cls="model_generated">
          {r.dependence.dates ? <Lines xTitle="month" yTitle="correlation" yfmt=".2f" lines={[{ name: "36m rolling", x: r.dependence.dates, y: r.dependence.rolling["36"] },
            { name: "DCC", x: r.dependence.dates, y: r.dependence.dcc.corr, width: 1 }]} shapes={(r.dependence.change_points?.dates ?? []).map((d: string) => ({ type: "line", x0: d, x1: d, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", width: 1, color: "#888" } }))} /> : null}
        </Viz>
        <Viz id="SC-06" title="Markov state transition matrix" question="Estimated transition matrix P, dwell durations, regime means/vols (label evidence) and state uncertainty." runId={runId} cls="model_generated"
          definition={"Mean max filtered probability " + pct(regs.mean_max_filtered_prob) + "; " + pct(regs.share_uncertain_months) + " of months have no state above 80% (state uncertainty)."}>
          {regs.transition ? <>
            <Matrix labels={regs.names} z={regs.transition} zTitle="P" />
            <DataTable rows={regs.names.map((n: string, i: number) => ({ n, dur: regs.expected_duration_months[i], st: regs.stationary[i], eq: regs.mu_annual[i][0], inf: regs.mu_annual[i][regs.mu_annual[i].length - 1], vol: regs.vol_annual[i][0] }))}
              columns={[{ key: "n", label: "state" }, { key: "dur", label: "dwell (months)", fmt: (v) => v.toFixed(1) }, { key: "st", label: "stationary", fmt: (v) => pct(v) },
                { key: "eq", label: "eq log-ret μ", fmt: (v) => pct(v) }, { key: "vol", label: "eq vol", fmt: (v) => pct(v) }, { key: "inf", label: "inflation μ", fmt: (v) => pct(v) }]} />
          </> : null}
        </Viz>
        <Viz id="SC-07" title="Copula tail dependence / exceedance" question="Student-t copula fit vs empirical joint tail exceedances (with sample counts and thresholds)." runId={runId} cls="observed">
          <DataTable rows={r.copula.empirical_tails} columns={[{ key: "q", label: "tail q", fmt: (v) => pct(v, 0) }, { key: "joint_exceedances", label: "joint exceedances" },
            { key: "expected_independent", label: "expected if independent", fmt: (v) => v.toFixed(1) }, { key: "n", label: "months" }, { key: "threshold_eq", label: "eq threshold", fmt: (v) => pct(v) }, { key: "threshold_bond", label: "bond threshold", fmt: (v) => pct(v) }]} />
          {r.copula.t_copula ? <div className="mt-2 text-xs">t-copula: {Object.entries(r.copula.t_copula).map(([k, v]: any) => k + " = " + (typeof v === "number" ? v.toFixed(3) : String(v))).join(" · ")}</div> : null}
        </Viz>
        <Viz id="SC-08" title="Inflation–rate–return scatter" question="Annual CPI inflation vs the change in the 10Y yield, coloured by the nominal bond return; dated points." runId={runId} cls="observed"
          definition={"Breakpoints (PELT on the return cross-product): " + (r.inflation_scatter.breakpoints.join(", ") || "none")}>
          <Scatter xTitle="CPI inflation (12m)" yTitle="Δ 10Y yield (12m)" xfmt=".0%" yfmt="+.1%" pts={[{ name: "years", x: r.inflation_scatter.cpi_yoy, y: r.inflation_scatter.d_yield_10y,
            text: r.inflation_scatter.dates.map((d: string, i: number) => d.slice(0, 4) + " · bond " + pct(r.inflation_scatter.bond_return_nominal[i])) }]} />
        </Viz>
        <Viz id="SC-09" title="Stress scenario matrix" question="Synthetic, model-generated shocks (rows) × portfolios (columns): increase in failure probability vs matched unstressed paths." runId={runId} cls="illustrative" definition={r.stress.note}
          table={() => <DataTable rows={r.stress.stresses.map((s: string, i: number) => ({ s, desc: r.stress.descriptions[s], ...Object.fromEntries(r.stress.portfolios.map((p: string, j: number) => [p, r.stress.d_fail[i][j]])) }))}
            columns={[{ key: "s", label: "stress" }, { key: "desc", label: "definition" }, ...r.stress.portfolios.map((p: string) => ({ key: p, label: p, fmt: (v: number) => spct(v, 1) }))]} />}>
          <Heat x={r.stress.portfolios} y={r.stress.stresses} z={r.stress.d_fail} xTitle="portfolio" yTitle="stress" zTitle="Δ P(failure)" zfmt="+.1%" zmin={0} />
          <Heat height={240} x={r.stress.portfolios} y={r.stress.stresses} z={r.stress.d_ce} diverging xTitle="portfolio" yTitle="stress" zTitle="ΔCE" zfmt="+.1%" />
        </Viz>
        <Viz id="SC-10" title="Retirement shock timing" question={"The same −35% equity shock in year 0, 5, 10 or 20 of retirement: success and median wealth (sequence risk isolated)."} runId={runId} cls="illustrative">
          <Seg label="portfolio" value={pf} onChange={setPf} options={Object.keys(r.shock_timing.portfolios).map((p) => ({ value: p, label: p }))} />
          <Lines xTitle="years since retirement" yTitle="median real wealth" yfmt="$,.0f" lines={r.shock_timing.portfolios[pf].map((row: any) => ({ name: "shock in year " + row.year, x: row.median_wealth_path.map((_: number, i: number) => i), y: row.median_wealth_path }))} />
          <Bars xTitle="shock year" yTitle="P(success)" yfmt=".0%" x={r.shock_timing.portfolios[pf].map((row: any) => "year " + row.year)} series={[{ name: "success", y: r.shock_timing.portfolios[pf].map((row: any) => row.success) }]} />
        </Viz>
        <Viz id="SC-11" title="Historical cohort start-date map" question={"Actual " + (r.cohorts.years ?? "") + "-year cohorts by start month: success (1) or failure (0) and terminal real wealth."} runId={runId} cls="observed"
          empty={r.cohorts.available ? null : r.cohorts.reason} definition={r.cohorts.caveat}>
          {r.cohorts.available ? <>
            <Heat height={200} x={r.cohorts.starts.filter((_: string, i: number) => i % 6 === 0)} y={cohortP} xTitle="cohort start" yTitle="portfolio" zTitle="success" zfmt=".0f" zmin={0} zmax={1} text={false}
              z={cohortP.map((p) => r.cohorts.portfolios[p].success.filter((_: boolean, i: number) => i % 6 === 0).map((v: boolean) => (v ? 1 : 0)))} />
            <Lines xTitle="cohort start" yTitle="terminal real wealth" yfmt="$,.0f" xType="date" lines={cohortP.map((p) => ({ name: p, x: r.cohorts.starts, y: r.cohorts.portfolios[p].terminal, width: 1.2 }))} />
          </> : null}
        </Viz>
        <Viz id="SC-12" title="Model mismatch diagnostics" question="PIT histograms of historical returns under each generator's simulated marginal; flags when uniformity fails (χ² p < 0.01)." runId={runId} cls="model_generated"
          definition="A well-calibrated marginal gives a flat PIT histogram. QLIKE out-of-sample covariance forecast comparison in the table below.">
          {r.pit[g] ? <Bars xTitle="PIT decile" yTitle="count" x={Array.from({ length: 10 }, (_, i) => String(i + 1))} series={Object.entries(r.pit[g]).map(([a, v]: any) => ({ name: a + (v.flag ? " ⚑" : ""), y: v.counts }))} /> : null}
          <DataTable rows={Object.entries(r.pit).flatMap(([gg, v]: any) => Object.entries(v).map(([a, s]: any) => ({ g: gg, a, chi2: s.chi2, p: s.p, flag: s.flag })))} columns={[{ key: "g", label: "generator" }, { key: "a", label: "asset" },
            { key: "chi2", label: "χ²", fmt: (v) => v.toFixed(1) }, { key: "p", label: "p", fmt: (v) => v.toExponential(1) }, { key: "flag", label: "red flag" }]} />
          {r.qlike ? <div className="mt-2 text-xs">QLIKE horse race: {JSON.stringify(r.qlike).slice(0, 300)}</div> : null}
        </Viz>
      </Grid>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{gens.map((x: string) => <Kpi key={x} label={x + " P(30y success), 60/40 4%"} value={pct(r.fans[x]?.success)} />)}</div>
    </div>
  );
}

export function Scenarios() {
  return (
    <div>
      <PageHeader eyebrow="Page H · F5" title="Scenario, Dependence & Stress Research"
        description="Are the generators credible? Distribution and tail fit, joint downside, regimes, tail dependence, a synthetic stress library and sequence-risk timing, plus actual historical cohorts — each labelled observed, modelled or illustrative." />
      <StudyGate kind="scenario_lab" title="Scenario diagnostics study" description="Fits all five generators on the duration universe and runs diagnostics, stress tests and cohort maps.">
        {(env) => <Body env={env} />}
      </StudyGate>
    </div>
  );
}
