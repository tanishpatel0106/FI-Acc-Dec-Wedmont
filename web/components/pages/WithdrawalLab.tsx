"use client";
import { useMemo, useState } from "react";
import { ExpandableCard } from "@/components/ui/expandable-card";
import { UtilitySweeps } from "@/components/research/withdrawal/UtilitySweeps";
import { ContextBar, DataTable, Grid, Kpi, Seg, StudyGate, Viz, Warnings, dataClassOf } from "@/components/research/kit";
import { ResearchPage, Sec } from "@/components/research/page";
import { Bars, Forest, Heat, Lines, Violin, ci, pct, usd } from "@/components/visualizations/charts";
import { useTrace } from "@/lib/api/v2";

/* eslint-disable @typescript-eslint/no-explicit-any */
const rFmt = (v: number) => (v * 100).toFixed(2) + "%";
const bFmt = (v: number) => (v * 100).toFixed(0) + "%";

function CellInspector({ runId, r, b, res, onClose, instance }: { runId: string; r: number; b: number; res: any; onClose?: () => void; instance?: string }) {
  const [path, setPath] = useState(0);
  const tr = useTrace(runId, { r, b, path });
  const ri = res.r.indexOf(r);
  const bi = res.b.indexOf(b);
  const mh = String(res.main_horizon);
  const t = tr.data?.trace;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">r = {rFmt(r)} · bond share {bFmt(b)} ({res.bond})</h2>
        {onClose ? <button className="text-xs underline" onClick={onClose}>close</button> : null}
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Kpi label={"P(success, " + mh + "y)"} value={pct(res.p_success[mh][bi][ri])} ci={ci(res.p_lo[mh][bi][ri], res.p_hi[mh][bi][ri])} />
        <Kpi label="P(no shortfall while alive)" value={pct(res.p_until_death[bi][ri])} />
        <Kpi label="CE consumption" value={usd(res.ce[bi][ri])} ci={"± " + usd(1.96 * res.ce_se[bi][ri])} />
        <Kpi label="Mean unmet spending" value={usd(res.unmet_mean[bi][ri])} sub={"CVaR95 " + usd(res.unmet_cvar95[bi][ri])} />
      </div>
      <Viz id="WL-11" instance={instance} title="Funding gap drilldown" question="Target vs funded real spending on one simulated path; when does the shortfall start?"
        runId={runId} selection={{ "withdrawal rate": rFmt(r), "bond share": bFmt(b), path }} cls="model_generated" definition="Desired = planned portfolio draw + income; funded = what the ledger could pay. The gap is booked as unmet spending and never counted as consumption.">
        <div className="mb-2 flex items-center gap-2 text-xs">path
          <input type="number" min={0} max={res.n_paths - 1} value={path} onChange={(e) => setPath(Math.max(0, Number(e.target.value)))}
            className="h-7 w-20 rounded border border-input bg-transparent px-2" />
          {t ? <span className="text-muted-foreground">first shortfall: {t.first_shortfall_month < 0 ? "none" : "month " + t.first_shortfall_month + " (year " + (t.first_shortfall_month / 12).toFixed(1) + ")"}</span> : null}
        </div>
        {t ? <Lines xTitle="age" yTitle="real $ per year" yfmt="$,.0f" lines={[
          { name: "desired spending", x: t.ages.slice(0, -1), y: t.desired_y, dash: "dot" },
          { name: "funded spending", x: t.ages.slice(0, -1), y: t.consumption_y },
          { name: "unmet", x: t.ages.slice(0, -1), y: t.unmet_y },
        ]} /> : <div className="h-60 animate-pulse rounded bg-muted/40" />}
        {t ? <Lines height={200} xTitle="age" yTitle="real wealth" yfmt="$,.0f" lines={[{ name: "wealth (start of year)", x: t.ages, y: t.wealth_y }]} /> : null}
      </Viz>
    </div>
  );
}

function Body({ env }: { env: any }) {
  const res = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(res);
  const [h, setH] = useState(String(res.main_horizon));
  const [target, setTarget] = useState(res.main_target.toFixed(2));
  const [cell, setCell] = useState<[number, number] | null>(null);
  const [rSel, setRSel] = useState("0.0500");
  const P = res.p_success[h] as number[][];
  const key = h + "|" + target;
  const th = res.thresholds[key] ?? [];
  const boot = res.threshold_bootstrap[key] ?? [];
  const rFine = res.r as number[];
  const noData = P.map((row: number[]) => row.map((v) => v === null));
  const detailKeys = Object.keys(res.details);
  const rDetails = [...new Set(detailKeys.map((k) => k.split("|")[0]))];
  const bDetails = [...new Set(detailKeys.map((k) => k.split("|")[1]))];
  const sel = rDetails.includes(rSel) ? rSel : rDetails[0];
  const frontierLines = useMemo(() => (res.targets as number[]).map((s: number) => {
    const k = h + "|" + s.toFixed(2);
    const rows = res.thresholds[k] ?? [];
    const bt = res.threshold_bootstrap[k] ?? [];
    return { name: "s* = " + (s * 100).toFixed(0) + "%", x: rows.map((r: any) => r.r),
      y: rows.map((r: any) => r.b_min), lo: bt.map((b: any) => b.q05), hi: bt.map((b: any) => b.q95) };
  }), [res, h]);
  const infeasible = th.filter((t: any) => t.status === "no_feasible_allocation").map((t: any) => t.r);
  const shapes = infeasible.length ? [{ type: "rect", xref: "x", yref: "paper", x0: Math.min(...infeasible) - res.r[1] / 2, x1: Math.max(...infeasible) + res.r[1] / 2,
    y0: 0, y1: 1, fillcolor: "rgba(127,127,127,0.12)", line: { width: 0 } }] : [];
  return (
    <div className="space-y-4">
      <ContextBar items={[["Universe", res.universe.name], ["Window", res.universe.window.join(" → ")], ["Generator", res.scenario.generator],
        ["Paths", res.n_paths], ["Bond", res.bond], ["Rebalancing", res.rebalancer], ["Goal", "fixed-horizon survival + CE"],
        ["Benchmark", "all-equity / fixed mixes"], ["Run", runId.slice(0, 10)], ["Evidence", "conditional (single model, MC CI)"]]} />
      <Warnings items={res.warnings} />
      <Sec id={["overview", "sustainability", "bond-necessity", "paths"]}><div className="flex flex-wrap gap-4">
        <Seg label="Horizon" value={h} onChange={setH} options={res.horizons.map((x: number) => ({ value: String(x), label: x + "y" }))} />
        <Seg label="Success target" value={target} onChange={setTarget} options={res.targets.map((x: number) => ({ value: x.toFixed(2), label: (x * 100).toFixed(0) + "%" }))} />
      </div></Sec>
      <Sec id="overview">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label={"Withdrawal breakpoint (" + (Number(target) * 100).toFixed(0) + "%)"} value={res.breakpoints[target] === null ? "Not established" : rFmt(res.breakpoints[target])}
          sub="first r where all-equity fails but a bond mix passes (main horizon)" />
        <Kpi label="Max r with a feasible mix" value={(() => { const ok = th.filter((t: any) => t.feasible_any); return ok.length ? rFmt(ok[ok.length - 1].r) : "none"; })()} sub={h + "y, grid bound"} />
        <Kpi label="b_min at 5%" value={(() => { const t = th.find((x: any) => Math.abs(x.r - 0.05) < 1e-9); return t ? (t.b_min === null ? "infeasible" : bFmt(t.b_min)) : "–"; })()}
          ci={(() => { const b = boot.find((x: any) => Math.abs(x.r - 0.05) < 1e-9); return b && b.q05 !== null ? "bootstrap 90%: " + bFmt(b.q05) + "–" + bFmt(b.q95) : undefined; })()} />
        <Kpi label="Paths / bootstrap" value={res.n_paths.toLocaleString()} sub={res.ci_method.slice(0, 80) + "…"} />
      </div>
      <Grid>
        <Viz id="WL-01" title="Withdrawal–bond survival probability" question={"P(no unmet spending through " + h + " years) by initial real withdrawal rate and Treasury share."}
          runId={runId} cls={cls} block="p_success" definition="Fixed-horizon financial survival on the selected generator. Click a cell for its CI, CE, until-death survival and a funding-gap drilldown."
          table={() => <DataTable columns={[{ key: "b", label: "bond", fmt: bFmt }, ...rFine.filter((_, i) => i % 4 === 0).map((r) => ({ key: String(r), label: rFmt(r), fmt: (v: any) => pct(v) }))]}
            rows={res.b.map((b: number, bi: number) => ({ b, ...Object.fromEntries(rFine.map((r, ri) => [String(r), P[bi][ri]])) }))} />}>
          <Heat x={rFine} y={res.b} z={P} xTitle="initial withdrawal rate" yTitle={res.bond + " share"} zTitle="P(success)" xfmt={rFmt} yfmt={bFmt}
            mask={noData} zmin={0} zmax={1} onClick={(i, j) => setCell([i, j])}
            contours={[{ level: Number(target), label: (Number(target) * 100).toFixed(0) + "%" }]} />
        </Viz>
        <Viz id="WL-02" title="Bond necessity frontier" question="Minimum bond share b_min achieving each success target; gaps = no feasible allocation."
          runId={runId} cls={cls} block="thresholds" definition="b_min = inf{b : P(b, r) >= s*} solved on the feasible set (non-monotone and disconnected sets allowed). Bands: joint path-bootstrap 5–95% of b_min. Shaded: no allocation meets the selected target."
          table={() => <DataTable columns={[{ key: "r", label: "r", fmt: rFmt }, { key: "b_min", label: "b_min", fmt: (v) => (v === null ? "none" : bFmt(v)) },
            { key: "status", label: "status" }, { key: "intervals", label: "feasible intervals", fmt: (v) => JSON.stringify(v) }]} rows={th} />}>
          <Lines lines={frontierLines} xTitle="initial withdrawal rate" yTitle="minimum bond share" xfmt=".1%" yfmt=".0%" yRange={[-0.02, 1.02]} shapes={shapes} />
        </Viz>
      </Grid>
      </Sec>
      <Sec id="sustainability"><Grid>
        <Viz id="WL-03" title="Survival curves by bond mix" question="Success probability across withdrawal rates for fixed bond shares; ribbons are Wilson 95% CIs."
          runId={runId} cls={cls} definition="Each curve holds the bond share fixed. Compare with the WL-10 generator overlay for model honesty.">
          <Lines xTitle="initial withdrawal rate" yTitle={"P(success, " + h + "y)"} xfmt=".1%" yfmt=".0%" lines={[0, 0.2, 0.4, 0.6, 0.8, 1].map((b) => {
            const bi = res.b.findIndex((x: number) => Math.abs(x - b) < 1e-9);
            return { name: "bond " + bFmt(b), x: rFine, y: P[bi], lo: res.p_lo[h][bi], hi: res.p_hi[h][bi] };
          })} />
        </Viz>
        <Viz id="WL-04" title="Maximum sustainable withdrawal" question="Largest grid withdrawal rate supporting each target, by bond share (bootstrap 5–95%)."
          runId={runId} cls={cls} definition="Model estimate on the selected generator and calibration window — not the historical '4% rule' (dotted reference), which came from US cohorts 1926–1976 (Bengen 1994).">
          <Lines xTitle="bond share" yTitle={"max r (" + res.main_horizon + "y)"} xfmt=".0%" yfmt=".2%"
            shapes={[{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0.04, y1: 0.04, line: { dash: "dot", width: 1, color: "#888" } }]}
            annotations={[{ xref: "paper", x: 0.99, y: 0.04, text: "historical 4% rule (reference)", showarrow: false, yanchor: "bottom", xanchor: "right", font: { size: 10 } }]}
            lines={Object.entries(res.max_sustainable).map(([s, rows]: any) => ({ name: "s* " + (Number(s) * 100).toFixed(0) + "%", x: rows.map((r: any) => r.b),
              y: rows.map((r: any) => r.max_r), lo: res.max_sustainable_boot[s]?.map((r: any) => r.q05), hi: res.max_sustainable_boot[s]?.map((r: any) => r.q95) }))} />
        </Viz>
      </Grid></Sec>
      <Sec id="utility">
        <Viz id="WL-05" title="CE-optimal vs survival-optimal bond share" question="Where do the welfare-maximising and survival-maximising allocations disagree?"
          runId={runId} cls={cls} definition="CE: CRRA certainty-equivalent of funded consumption (mortality-weighted). Survival: fixed-horizon P(success). Distance = |b_CE − b_survival|."
          table={() => <DataTable columns={[{ key: "r", label: "r", fmt: rFmt }, { key: "b_ce", label: "b CE", fmt: bFmt }, { key: "b_survival", label: "b surv", fmt: bFmt },
            { key: "ce_at_ce_opt", label: "CE@CE", fmt: usd }, { key: "ce_at_surv_opt", label: "CE@surv", fmt: usd }, { key: "p_at_ce_opt", label: "P@CE", fmt: (v) => pct(v) },
            { key: "p_at_surv_opt", label: "P@surv", fmt: (v) => pct(v) }]} rows={res.optima} />}>
          <Lines xTitle="initial withdrawal rate" yTitle="optimal bond share" xfmt=".1%" yfmt=".0%" lines={[
            { name: "CE-optimal", x: res.optima.map((o: any) => o.r), y: res.optima.map((o: any) => o.b_ce), mode: "lines+markers" },
            { name: "survival-optimal", x: res.optima.map((o: any) => o.r), y: res.optima.map((o: any) => o.b_survival), mode: "lines+markers", dash: "dash" }]} />
        </Viz>
      </Sec>
      <Sec id="robustness"><Grid>
        <Viz id="WL-06" title="Threshold sensitivity (r = 5%)" question="How does b_min move with target, horizon, generator, calibration window and risk aversion?"
          runId={runId} cls={cls} definition="Markers: point b_min; bars: bootstrap 5–95% where computed. 'not identified' = no feasible allocation; γ rows show the CE-optimal share instead.">
          <Forest xTitle="bond share" xfmt=".0%" ref={null} rows={res.forest.map((f: any) => ({ label: f.dimension + ": " + f.label, est: f.b_min, lo: f.lo, hi: f.hi,
            note: f.b_min === null ? (f.status ?? "").replace(/_/g, " ") : f.status }))} />
        </Viz>
        <Viz id="WL-10" title="Model disagreement overlay" question={"Cells where every generator agrees on feasibility at the " + (res.main_target * 100).toFixed(0) + "% target vs cells that are not stable."}
          runId={runId} cls={cls} definition={"Models: " + ["main", ...Object.keys(res.alt_generators)].join(", ") + ". 1 = all models agree (feasible or infeasible); cross = disagreement ('not stable')."}>
          <Heat x={res.agreement.r} y={res.agreement.b} z={res.agreement.feasible_all} xTitle="withdrawal rate" yTitle="bond share" zTitle="feasible under all"
            xfmt={rFmt} yfmt={bFmt} zfmt=".1f" zmin={0} zmax={1} mask={res.agreement.agree.map((r: number[]) => r.map((v) => v === 0))} text={false} />
        </Viz>
      </Grid></Sec>
      <Sec id="outcomes">
      <div className="flex flex-wrap items-center gap-3">
        <Seg label="Policy detail at withdrawal" value={sel} onChange={setRSel} options={rDetails.map((r) => ({ value: r, label: rFmt(Number(r)) }))} />
      </div>
      <Grid>
        <Viz id="WL-07" title="First-shortfall cumulative probability" question="Probability of a first unmet withdrawal by year after retirement."
          runId={runId} cls={cls} definition="Solid: financial (fixed horizon). Dotted: weighted by the probability of being alive at that time (SSA period table) — shortfalls after death do not count.">
          <Lines xTitle="years after retirement" yTitle="cumulative probability" yfmt=".0%" lines={bDetails.flatMap((b, i) => {
            const d = res.details[sel + "|" + b]; if (!d) return [];
            return [{ name: "bond " + bFmt(Number(b)), x: d.first_shortfall.years, y: d.first_shortfall.cumulative, color: undefined },
              ...(i === 2 ? [{ name: "bond " + bFmt(Number(b)) + " (alive)", x: d.first_shortfall.years, y: d.first_shortfall.cumulative_alive, dash: "dot" }] : [])];
          })} />
        </Viz>
        <Viz id="WL-08" title="First-shortfall timing (conditional on failure)" question="When does the first shortfall happen, among paths that fail? The no-failure mass is reported separately."
          runId={runId} cls={cls}>
          <Bars xTitle="year after retirement" yTitle="share of paths" yfmt=".1%" x={res.details[sel + "|" + bDetails[0]]?.first_shortfall.years ?? []}
            series={bDetails.filter((_, i) => i % 2 === 0).map((b) => { const d = res.details[sel + "|" + b]; const tot = res.n_paths;
              return { name: "bond " + bFmt(Number(b)) + " (no failure " + pct(d.first_shortfall.no_failure_share, 0) + ")", y: d.first_shortfall.histogram_years.map((v: number) => v / tot) }; })} />
        </Viz>
        <Viz id="WL-09" title="Shortfall severity" question="Unmet real spending (summed over the horizon) among failing paths; unconditional mean and CVaR in the table."
          runId={runId} cls={cls} definition="Conditional = given a shortfall occurs; unconditional = averaged over all paths (zeros included). CVaR95 = mean of the worst 5%."
          table={() => <DataTable columns={[{ key: "b", label: "bond" }, { key: "p_fail", label: "P(fail)", fmt: (v) => pct(v) }, { key: "mean_unconditional", label: "mean (all)", fmt: usd },
            { key: "cvar95_unconditional", label: "CVaR95 (all)", fmt: usd }, { key: "mean_conditional", label: "mean | fail", fmt: usd }, { key: "cvar95_conditional", label: "CVaR95 | fail", fmt: usd }]}
            rows={bDetails.map((b) => ({ b: bFmt(Number(b)), ...res.details[sel + "|" + b].severity }))} />}>
          {bDetails.some((b) => res.details[sel + "|" + b].severity.sample_conditional) ? (
            <Violin yTitle="unmet real $ (conditional)" groups={bDetails.filter((b) => res.details[sel + "|" + b].severity.sample_conditional)
              .map((b) => ({ name: "bond " + bFmt(Number(b)), y: res.details[sel + "|" + b].severity.sample_conditional }))} />
          ) : <div className="py-10 text-center text-xs text-muted-foreground">No failing paths at this withdrawal rate.</div>}
        </Viz>
      </Grid></Sec>
      <Sec id="bond-necessity"><Grid>
        <Viz id="WL-12" title="Model-conditional allocation ranges by remaining horizon" question="Feasible bond-share intervals and CE-best mix at a 4% withdrawal, by horizon (a proxy for retirement phase)."
          runId={runId} cls={cls} definition="Model-conditional research ranges for the stated inputs — not personalised advice. Empty = no feasible allocation.">
          <DataTable columns={[{ key: "horizon_years", label: "horizon" }, { key: "status", label: "status" },
            { key: "feasible_intervals", label: "feasible bond intervals", fmt: (v) => (v?.length ? v.map((x: number[]) => bFmt(x[0]) + "–" + bFmt(x[1])).join(", ") : "none") },
            { key: "b_min", label: "b_min", fmt: (v) => (v === null ? "–" : bFmt(v)) }, { key: "b_min_ci", label: "b_min 90%", fmt: (v) => (v?.[0] === null || v?.[0] === undefined ? "–" : bFmt(v[0]) + "–" + bFmt(v[1])) },
            { key: "b_ce", label: "CE-best b", fmt: bFmt }]} rows={res.phases} />
        </Viz>
        <Viz id="FI-12" title="Bond value across the withdrawal spectrum" question="Change in success from moving 40% of an all-equity portfolio into each instrument."
          runId={runId} cls={cls} instance="withdrawal" definition="Paired on identical paths. TIPS appear only in universes that contain them.">
          <Lines xTitle="withdrawal rate" yTitle="Δ P(success)" xfmt=".1%" yfmt="+.0%" lines={res.bond_spectrum.filter((b: any) => b.available).map((b: any) => ({ name: b.bond, x: b.r, y: b.d_success, mode: "lines+markers" }))} />
        </Viz>
      </Grid></Sec>
      <Sec id="paths"><PathExplorer runId={runId} res={res} /></Sec>
      <ExpandableCard open={!!cell} layoutId="wl-cell" onClose={() => setCell(null)}>
        {cell ? <CellInspector runId={runId} r={rFine[cell[1]]} b={res.b[cell[0]]} res={res} onClose={() => setCell(null)} instance="cell" /> : null}
      </ExpandableCard>
    </div>
  );
}

function PathExplorer({ runId, res }: { runId: string; res: any }) {
  const [r, setR] = useState(0.05);
  const [b, setB] = useState(0.4);
  const rs = (res.r as number[]).filter((_, i) => i % 2 === 0);
  const bs = res.b as number[];
  const near = (xs: number[], v: number) => xs.reduce((a, x) => (Math.abs(x - v) < Math.abs(a - v) ? x : a), xs[0]);
  const rr = near(res.r, r), bb = near(bs, b);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-4 text-xs">
        <label className="flex flex-col gap-1">Initial withdrawal rate
          <select aria-label="Initial withdrawal rate" className="h-8 rounded border border-input bg-transparent px-2" value={rr} onChange={(e) => setR(Number(e.target.value))}>
            {rs.map((x) => <option key={x} value={x}>{rFmt(x)}</option>)}
          </select></label>
        <label className="flex flex-col gap-1">Bond share ({res.bond})
          <select aria-label="Bond share" className="h-8 rounded border border-input bg-transparent px-2" value={bb} onChange={(e) => setB(Number(e.target.value))}>
            {bs.map((x) => <option key={x} value={x}>{bFmt(x)}</option>)}
          </select></label>
        <span className="text-muted-foreground">Or click any cell of the survival heatmap (WL-01) in Research Overview.</span>
      </div>
      <CellInspector runId={runId} r={rr} b={bb} res={res} />
    </div>
  );
}

/** Withdrawal Lab: survival surfaces, bond necessity, utility sweeps, shortfall outcomes, robustness and paths. */
export function WithdrawalLab() {
  return (
    <ResearchPage page="withdrawal">
      <StudyGate kind="frontier" title="Bond-necessity frontier study"
        description="2,000 bootstrap paths × 41 withdrawal rates × 21 bond shares, horizons 10–40y, joint bootstrap of b_min, alternative generators and windows (~20 s).">
        {(env) => <Body env={env} />}
      </StudyGate>
      <Sec id="utility">
        <h2 className="mt-8 text-base font-semibold">Certainty-equivalent utility sweeps</h2>
        <UtilitySweeps />
      </Sec>
    </ResearchPage>
  );
}
