"use client";
import { useState } from "react";
import { ContextBar, DataTable, Grid, Kpi, Seg, StudyGate, Viz, Warnings, dataClassOf } from "@/components/research/kit";
import { Bars, Fan, Forest, Heat, Lines, pct, spct, useAssetColor, usd } from "@/components/visualizations/charts";
import { useTrace } from "@/lib/api/v2";
import { Tex } from "@/components/common/Tex";
import { ResearchPage, Sec } from "@/components/research/page";
import { Simulator } from "@/components/research/lifecycle/Simulator";
import { HistoricalReplay } from "@/components/research/lifecycle/HistoricalReplay";

/* eslint-disable @typescript-eslint/no-explicit-any */
const qFmt = (v: number) => (v > 0 ? "+" : "") + (v * 100).toFixed(1) + "%";

function Persona({ res, runId }: { res: any; runId: string }) {
  const p = res.persona;
  const [pol, setPol] = useState<"target_date" | "q_aware_plan">("target_date");
  const [path, setPath] = useState(0);
  const tr = useTrace(runId, { policy: "target_date", path });
  const color = useAssetColor();
  const d = p.policies[pol];
  const ages = d.wealth_fan.p50.map((_: number, i: number) => p.start_age + i);
  const t = tr.data?.trace;
  const rebYears: number[] = [];
  if (t) t.monthly.reason.forEach((r: number, m: number) => { if (r >= 2 && r <= 6) rebYears.push(p.start_age + m / 12); });
  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <Seg label="Persona policy" value={pol} onChange={setPol} options={[{ value: "target_date", label: "Age-based target-date" }, { value: "q_aware_plan", label: "q-aware planned schedule" }]} />
        <span className="text-xs text-muted-foreground">{p.label}: age {p.start_age}, income {usd(p.income)}, saves {pct(p.savings_rate, 0)}, retires {p.retirement_age}, pension {usd(p.pension)}, {pct(p.withdrawal_rate, 0)} fixed real draw</span>
      </div>
      <Grid>
        <Viz id="LC-04" title="Lifecycle wealth and consumption fan" question="Real wealth and funded consumption across age for the synthetic persona; dashed line = retirement."
          runId={runId} cls={dataClassOf(res)} definition="Percentile bands 5–95 / 25–75 / median across simulated paths. Consumption = labour income net of saving before retirement; pension + funded draw after.">
          <Fan x={[...ages, ages[ages.length - 1] + 1]} q={d.wealth_fan} name="wealth" xTitle="age" yTitle="real wealth" vline={{ x: p.retirement_age, label: "retirement" }} />
          <Fan height={220} x={ages} q={d.consumption_fan} name="funded consumption" xTitle="age" yTitle="real $ / year" vline={{ x: p.retirement_age, label: "retirement" }} />
        </Viz>
        <Viz id="LC-07" title="Policy transition map" question="Mean target weights by years relative to retirement, with the planned signed net flow."
          runId={runId} cls={dataClassOf(res)} definition="Universe sleeves only (equity / nominal Treasury / T-bills in the public universe). TIPS and gold require universes that contain them. Planned q: −5% early accumulation, −2% late accumulation, +4% in retirement.">
          <Bars stacked xTitle="years relative to retirement" yTitle="weight" yfmt=".0%" x={p.years_relative.slice(0, d.weights_by_year.length)}
            series={p.assets.map((a: string, ai: number) => ({ name: a, color: color(a, ai), y: d.weights_by_year.map((w: number[]) => w[ai]) }))} />
          <Lines height={160} xTitle="years relative to retirement" yTitle="planned q" yfmt="+.0%" lines={[{ name: "planned net draw q", x: p.years_relative, y: p.planned_q }]} />
        </Viz>
        <Viz id="LC-08" title="Human-centred path story (synthetic persona)" question="One labelled synthetic path: phase transitions, funding, rebalancing events and the equations behind them."
          runId={runId} cls="illustrative" definition="Synthetic, labelled persona — not an inferred real household. Target-date policy, path chosen by the slider.">
          <div className="mb-2 flex items-center gap-2 text-xs">path <input type="number" min={0} max={999} value={path} onChange={(e) => setPath(Math.max(0, Number(e.target.value)))}
            className="h-7 w-20 rounded border border-input bg-transparent px-2" /></div>
          {t ? <>
            <Lines xTitle="age" yTitle="real $" yfmt="$,.0f" lines={[{ name: "wealth", x: t.ages, y: t.wealth_y }]}
              shapes={[{ type: "line", x0: p.retirement_age, x1: p.retirement_age, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", width: 1, color: "#888" } },
                ...rebYears.map((x) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 0.06, line: { width: 1, color: "#888" } }))]} />
            <div className="grid gap-2 text-xs md:grid-cols-3">
              <div className="rounded border border-border p-2"><b>Accumulation</b> (age {p.start_age}–{p.retirement_age}): contributions = saving × labour income; ticks = {rebYears.length} rebalancing trades.</div>
              <div className="rounded border border-border p-2"><b>Transition</b> at {p.retirement_age}: initial draw = 4% × wealth, fixed in real terms.</div>
              <div className="rounded border border-border p-2"><b>Decumulation</b>: first shortfall {t.first_shortfall_month < 0 ? "never" : "at age " + (p.start_age + t.first_shortfall_month / 12).toFixed(1)}.</div>
            </div>
            <div className="mt-2 space-y-1 text-xs">{p.equations.map((e: string) => <div key={e}><Tex>{e.replace(/_\{([^}]+)\}/g, "_{$1}")}</Tex></div>)}</div>
          </> : <div className="h-60 animate-pulse rounded bg-muted/40" />}
        </Viz>
        <Viz id="LC-06" title="Accumulation contribution frontier" question={p.contribution_frontier.definition}
          runId={runId} cls={dataClassOf(res)} definition="Compare the age-based glidepath with the q-aware planned schedule. Same labour-income draws and returns (paired).">
          <Heat x={p.contribution_frontier.savings} y={p.contribution_frontier.start_ages} z={p.contribution_frontier.policies[pol]}
            xTitle="savings rate" yTitle="start age" zTitle="P(target)" xfmt={(v) => pct(v, 0)} zmin={0} zmax={1} />
        </Viz>
      </Grid>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {(["target_date", "q_aware_plan"] as const).map((k) => <Kpi key={k} label={(k === "target_date" ? "Target-date" : "q-aware") + ": P(no shortfall to 95)"}
          value={pct(p.policies[k].p_success_to_95)} sub={"CE " + usd(p.policies[k].ce) + " · " + p.policies[k].rebalances_per_year.toFixed(2) + " rebalances/yr"} />)}
      </div>
    </>
  );
}

function Body({ env }: { env: any }) {
  const res = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(res);
  const [obj, setObj] = useState<"ce" | "survival">("ce");
  const [ageSel, setAgeSel] = useState(String(res.ages[Math.floor(res.ages.length / 2)]));
  const z = obj === "ce" ? res.b_ce : res.b_survival;
  const zeroIdx = res.q.indexOf(0);
  const ai = res.ages.indexOf(Number(ageSel));
  const fr = res.funded_ratio.map((r: (number | null)[]) => r.map((v) => (v === null ? null : Math.min(v, 5))));
  return (
    <div className="space-y-4">
      <ContextBar items={[["Universe", res.universe.name], ["Window", res.universe.window.join(" → ")], ["Paths", res.n_paths + " test / train disjoint"],
        ["q", "planned, exogenous"], ["Objective", obj], ["W_ref", "$1,000,000"], ["Run", runId.slice(0, 10)], ["Evidence", "conditional"]]} />
      <Warnings items={res.warnings} />
      <Sec id={["overview", "policies", "funding"]}><div className="flex flex-wrap gap-4"><Seg label="Objective" value={obj} onChange={setObj} options={[{ value: "ce", label: "CE of resources" }, { value: "survival", label: "Survival" }]} /></div></Sec>
      <Sec id="overview">
        <Viz id="LC-01" title="Signed-q allocation surface" question="Optimal bond share by planned signed net-draw rate (negative = contributions) and age."
          runId={runId} cls={cls} block="b_ce" definition={res.definitions.q + ". " + res.definitions.ce + ". Optimised on training paths; LC-02 scores out of sample. Zero-flow column highlighted."}
          table={() => <DataTable columns={[{ key: "age", label: "age" }, ...res.q.map((q: number, i: number) => ({ key: String(i), label: qFmt(q), fmt: (v: any) => pct(v, 0) }))]}
            rows={res.ages.map((a: number, i: number) => ({ age: a, ...Object.fromEntries(z[i].map((v: number, j: number) => [String(j), v])) }))} />}>
          <Heat x={res.q} y={res.ages} z={z} xTitle="planned signed net draw q (per year, % of W_ref)" yTitle="age" zTitle="bond share" xfmt={qFmt} zmin={0} zmax={1} />
          <div className="text-[11px] text-muted-foreground">Zero flow column: q = {qFmt(res.q[zeroIdx] ?? 0)} · test-optimal surface differs from the training optimum in {(() => { let n = 0, d = 0; res.b_ce.forEach((r: number[], i: number) => r.forEach((v, j) => { n++; if (v !== res.b_ce_test_optimal[i][j]) d++; })); return d + " of " + n; })()} cells.</div>
        </Viz>
        <div className="flex items-center gap-3"><Seg label="Age slice" value={ageSel} onChange={setAgeSel} options={res.ages.map((a: number) => ({ value: String(a), label: String(a) }))} /></div>
        <Viz id="LC-01b" title={"Optimal bond share across q at age " + ageSel} question="Cross-section of LC-01 with survival-optimal share and test-path survival at the CE optimum." runId={runId} cls={cls}>
          <Lines xTitle="planned net draw q" yTitle="share / probability" xfmt="+.0%" yfmt=".0%" lines={[
            { name: "CE-optimal bond share", x: res.q, y: res.b_ce[ai], mode: "lines+markers" },
            { name: "survival-optimal bond share", x: res.q, y: res.b_survival[ai], mode: "lines+markers", dash: "dash" },
            { name: "test P(no shortfall) at CE optimum", x: res.q, y: res.survival_test_at_ce_opt[ai], dash: "dot" }]} />
        </Viz>
      </Sec>
      <Sec id="policies"><Grid>
        <Viz id="LC-02" title="Age-only vs q-only vs full policy" question="Out-of-sample CE loss of restricted policies relative to the cell-optimal (age + q) policy."
          runId={runId} cls={cls} definition={res.policies.note + ". Association within the model, not a causal effect on households."}>
          <div className="mb-2 grid grid-cols-3 gap-2">
            {(["age_only", "q_only", "target_date"] as const).map((k) => <Kpi key={k} label={k.replace("_", "-")} value={spct(res.policies.oos_mean_delta[k])}
              ci={"95% CI " + spct(res.policies.oos_delta_ci[k][0]) + " to " + spct(res.policies.oos_delta_ci[k][1])} />)}
          </div>
          <Heat height={240} x={res.q} y={res.ages} z={res.policies.oos_delta_vs_full.age_only} xTitle="q" yTitle="age" zTitle="ΔCE age-only" xfmt={qFmt} diverging zfmt=".1%" text={false} />
          <Heat height={240} x={res.q} y={res.ages} z={res.policies.oos_delta_vs_full.q_only} xTitle="q" yTitle="age" zTitle="ΔCE q-only" xfmt={qFmt} diverging zfmt=".1%" text={false} />
        </Viz>
        <Viz id="LC-03" title="Controlled marginal slopes ∂b*/∂q" question="Slope of the optimal bond share in q at fixed age, with path-bootstrap 95% intervals; zero = no effect."
          runId={runId} cls={cls} definition="Global: OLS slope over the q grid. Local: finite difference around q = 0. Units: change in bond share per 100% of W_ref per year (0.01 = 1pp per 1pp of q).">
          <Forest xTitle="∂ bond share / ∂ q" refLabel="no effect" rows={res.slopes.map((s: any) => ({ label: "age " + s.age, est: s.slope, lo: s.lo, hi: s.hi }))} />
          <Forest xTitle="local slope at q = 0" rows={res.slopes.map((s: any) => ({ label: "age " + s.age + " (local)", est: s.local_slope_at_zero, lo: s.local_lo, hi: s.local_hi }))} />
        </Viz>
      </Grid></Sec>
      <Sec id="funding">
        <Viz id="LC-05" title="Funded ratio and liquidity map" question="W_ref / PV(planned real net draws) by age and q; net contributors carry no portfolio liability."
          runId={runId} cls={cls} definition={res.funded_ratio_basis.definition + ". Real rate " + pct(res.funded_ratio_basis.real_rate, 2) + " (" + res.funded_ratio_basis.source + "), " + res.funded_ratio_basis.mortality + ". Capped at 5× for colour."}>
          <Heat x={res.q} y={res.ages} z={fr} xTitle="q" yTitle="age" zTitle="funded ratio" xfmt={qFmt} zfmt=".2f" mask={res.funded_ratio.map((r: any[]) => r.map((v) => v === null))} />
        </Viz>
      </Sec>
      <Sec id="household"><Persona res={res} runId={runId} /></Sec>
    </div>
  );
}

/** Lifecycle & Cash Flows: signed-flow allocation, policy restrictions, funding, household paths and the interactive simulator. */
export function LifecycleFlows() {
  return (
    <ResearchPage page="lifecycle">
      <Sec id={["overview", "policies", "funding", "household"]}>
        <StudyGate kind="signed_flow" title="Signed-flow study" description="7 ages × 19 planned q values × 11 bond shares, train/test seed sets, path bootstrap of slopes, plus a synthetic lifecycle persona.">
          {(env) => <Body env={env} />}
        </StudyGate>
      </Sec>
      <Sec id="replay"><HistoricalReplay /></Sec>
      <Sec id="simulator"><Simulator /></Sec>
    </ResearchPage>
  );
}
