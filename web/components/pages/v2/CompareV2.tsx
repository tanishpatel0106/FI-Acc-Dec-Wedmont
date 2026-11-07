"use client";
import { useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/common/Section";
import { Compare as LegacyCompare } from "@/components/pages/Compare";
import { ContextBar, DataTable, Empty, Grid, PageTabs, StudyGate, Viz, Warnings, dataClassOf } from "@/components/v2/kit";
import { Bars, Fan, Forest, Heat, Lines, Scatter, Waterfall, pct, spct, usd } from "@/components/v2/charts";
import { useVizTokens } from "@/components/charts/Plot";

/* eslint-disable @typescript-eslint/no-explicit-any */
function Body({ env }: { env: any }) {
  const r = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(r);
  const t = useVizTokens();
  const sc = r.scatter;
  const fail = sc.policy_failed.map((f: boolean, i: number) => f || sc.benchmark_failed[i]);
  const ages = r.twin_fan.ages;
  const att = r.attribution;
  return (
    <div className="space-y-4">
      <ContextBar items={[["Universe", r.universe.name], ["Benchmark", r.benchmark], ["Focus policy", r.focus], ["Withdrawal", pct(r.withdrawal, 1)], ["Paths", r.n_paths],
        ["Sign reversal across models", r.sign_reversal ? "YES ⚠" : "no"], ["Run", runId.slice(0, 10)]]} />
      <Warnings items={[...r.warnings, ...(r.sign_reversal ? ["The sign of ΔCE reverses across generators/windows (CO-08): treat the comparison as model-dependent."] : [])]} />
      <Grid>
        <Viz id="CO-01" title="Paired CE forest plot" question={"Policy minus " + r.benchmark + ": paired ΔCE with shared sampling (path-bootstrap 95% CI)."} runId={runId} cls={cls} block="forest">
          <Forest xTitle={"ΔCE vs " + r.benchmark} xfmt="+.1%" refLabel="no difference" rows={r.forest.map((f: any) => ({ label: f.policy, est: f.delta, lo: f.lo, hi: f.hi }))} />
        </Viz>
        <Viz id="CO-02" title="Paired path scatter" question={"Per-path CE: " + r.benchmark + " (x) vs " + r.focus + " (y); points above the diagonal favour the policy; failures highlighted."} runId={runId} cls={cls}>
          <Scatter diagonal xTitle={r.benchmark + " path CE"} yTitle={r.focus + " path CE"} xfmt="$,.0f" yfmt="$,.0f" pts={[
            { name: "no failure", x: sc.benchmark_ce.filter((_: number, i: number) => !fail[i]), y: sc.policy_ce.filter((_: number, i: number) => !fail[i]), size: 5 },
            { name: "a shortfall in either", x: sc.benchmark_ce.filter((_: number, i: number) => fail[i]), y: sc.policy_ce.filter((_: number, i: number) => fail[i]), size: 7, color: t.series[1], symbol: "x" }]} />
        </Viz>
        <Viz id="CO-03" title="Twin wealth / consumption fan" question="Same path innovations and withdrawal budget for both policies." runId={runId} cls={cls}>
          <Fan x={ages} q={r.twin_fan.policy.wealth} name={r.focus} compare={{ q: r.twin_fan.benchmark.wealth, name: r.benchmark }} xTitle="age" yTitle="real wealth" />
          <Fan height={220} x={ages.slice(0, -1)} q={r.twin_fan.policy.consumption} name={r.focus} compare={{ q: r.twin_fan.benchmark.consumption, name: r.benchmark }} xTitle="age" yTitle="funded consumption" />
        </Viz>
        <Viz id="CO-04" title="Divergent path explorer" question="The largest negative and positive path differences, with the early-sequence explanation (first-5-year real equity return and CPI)." runId={runId} cls={cls}>
          <DataTable rows={r.divergent} columns={[{ key: "group", label: "group" }, { key: "path", label: "path" }, { key: "delta_path_ce", label: "Δ path CE", fmt: usd },
            { key: "equity_real_return_first_5y", label: "equity 5y real", fmt: (v) => pct(v) }, { key: "cpi_first_5y", label: "CPI 5y", fmt: (v) => pct(v) },
            { key: "policy_first_shortfall_year", label: "policy 1st shortfall (y)", fmt: (v) => (v === null ? "none" : v.toFixed(1)) },
            { key: "benchmark_first_shortfall_year", label: "bench 1st shortfall (y)", fmt: (v) => (v === null ? "none" : v.toFixed(1)) },
            { key: "terminal_policy", label: "terminal policy", fmt: usd }, { key: "terminal_benchmark", label: "terminal bench", fmt: usd }]} />
        </Viz>
        <Viz id="CO-05" title="Cohort winner matrix" question="Actual historical start years × policy: path-CE relative to the benchmark (blank = outside coverage)." runId={runId} cls="observed"
          empty={r.cohorts.available ? null : r.cohorts.reason} definition={r.cohorts.caveat + "; coverage " + (r.cohorts.coverage ?? []).join(" → ")}>
          {r.cohorts.available ? <Heat x={r.cohorts.years} y={r.cohorts.policies} z={r.cohorts.delta_path_ce} diverging xTitle="cohort start year" yTitle="policy" zTitle="Δ path CE" zfmt="+.0%" text={false} /> : null}
        </Viz>
        <Viz id="CO-06" title="Trade-off table" question="CE, survival, shortfall, drawdown, cost and data quality per policy; sortable, exportable." runId={runId} cls={cls} block="table">
          <DataTable rows={r.table} columns={[{ key: "policy", label: "policy" }, { key: "ce", label: "CE", fmt: usd }, { key: "success", label: "P(success)", fmt: (v) => pct(v) },
            { key: "unmet_mean", label: "mean unmet", fmt: usd }, { key: "mdd_median", label: "median MDD", fmt: (v) => pct(v) }, { key: "cost_bps_yr", label: "cost bps/yr", fmt: (v) => v.toFixed(2) },
            { key: "data_quality", label: "data quality" }]} />
        </Viz>
        <Viz id="CO-07" title="Attribution waterfall" question={"How much of the CE change from " + r.benchmark + " to " + r.focus + "-style choices comes from allocation, spending, rebalancing and costs?"} runId={runId} cls={cls} definition={att.note}>
          <Waterfall yTitle="CE ($/yr)" labels={["base CE", ...att.sequential.map((s: any) => s.factor)]} values={[att.base_ce, ...att.sequential.map((s: any) => s.delta_ce_usd)]} totalLabel="full" />
          <Bars xTitle="factor" yTitle="Shapley CE ($/yr)" yfmt="$,.0f" x={Object.keys(att.shapley)} series={[{ name: "Shapley (order-free)", y: Object.values(att.shapley) as number[] },
            { name: "sequential", y: att.sequential.map((s: any) => s.delta_ce_usd) }]} />
          <div className="text-[11px] text-muted-foreground">{Object.entries(att.definitions).map(([k, v]: any) => k + ": " + v).join(" · ")}</div>
        </Viz>
        <Viz id="CO-08" title="Regime robustness forest" question="ΔCE of the focus policy across generators and calibration windows; sign reversals flagged." runId={runId} cls={cls}>
          <Forest xTitle="ΔCE vs benchmark" xfmt="+.1%" rows={r.robustness.map((x: any) => ({ label: x.label + (x.iid === false ? " (cohorts)" : ""), est: x.error ? null : x.delta, lo: x.lo, hi: x.hi, note: x.error }))} />
        </Viz>
        <Viz id="CO-09" title="Model-source substitution sensitivity" question="Public repriced vs WRDS observed returns on the same overlap: mean difference, tracking error, correlation." runId={runId} cls="observed"
          empty={r.source_substitution.available ? null : r.source_substitution.reason}>
          {r.source_substitution.available ? <DataTable rows={r.source_substitution.rows} columns={[{ key: "series_id", label: "series" }, { key: "sources", label: "sources", fmt: (v) => v.join(" vs ") },
            { key: "overlap_months", label: "overlap" }, { key: "mean_diff_annual", label: "mean diff/yr", fmt: (v) => spct(v) }, { key: "tracking_error_annual", label: "TE", fmt: (v) => pct(v) }, { key: "corr", label: "corr", fmt: (v) => v.toFixed(3) }]} /> : null}
        </Viz>
        <Viz id="CO-10" title="Historical first-failure timeline" question={"Worst observed cohort (start " + (r.cohorts.timeline?.cohort_start ?? "–") + "): desired vs funded real spending and gap by year."} runId={runId} cls="observed"
          empty={r.cohorts.available ? null : r.cohorts.reason}>
          {r.cohorts.timeline ? <Lines xTitle="years since start" yTitle="real $ / yr" yfmt="$,.0f" lines={[
            { name: "desired", x: r.cohorts.timeline.years, y: r.cohorts.timeline.desired, dash: "dot" }, { name: "funded (" + r.cohorts.timeline.policy + ")", x: r.cohorts.timeline.years, y: r.cohorts.timeline.funded },
            { name: "unmet (" + r.cohorts.timeline.policy + ")", x: r.cohorts.timeline.years, y: r.cohorts.timeline.unmet }, { name: "unmet (benchmark)", x: r.cohorts.timeline.years, y: r.cohorts.timeline.benchmark_unmet, dash: "dash" }]} /> : <Empty>no timeline</Empty>}
        </Viz>
      </Grid>
    </div>
  );
}

export function CompareV2() {
  const params = useSearchParams();
  return (
    <div>
      <PageHeader eyebrow="Page J · F6" title="Policy & Historical Cohort Comparison"
        description="Paired comparisons on shared paths, actual historical cohorts, order-free attribution, and robustness across generators and calibration windows. Legacy run-vs-run comparison (compare saved runs by ID) is in the second tab." />
      <PageTabs initial={params.get("id") ? "legacy" : "v2"} tabs={[
        { title: "Policy comparison (v2)", value: "v2", content: <StudyGate kind="compare_v2" title="Policy comparison study">{(env) => <Body env={env} />}</StudyGate> },
        { title: "Compare saved runs (legacy)", value: "legacy", content: <LegacyCompare /> }]} />
    </div>
  );
}
