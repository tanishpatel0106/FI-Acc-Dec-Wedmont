"use client";
import { ResearchPage, Sec } from "@/components/research/page";
import { HypothesisTests, RunValidation, usePickableRuns } from "@/components/research/compare/SavedRunAnalytics";
import { DataTable, Grid, GradeTag, StudyGate, Viz } from "@/components/research/kit";
import { Forest, Heat, Lines, SampleHist, pct } from "@/components/visualizations/charts";
import { useVizTokens } from "@/components/visualizations/Plot";
import { Plot } from "@/components/visualizations/Plot";
import type { Data } from "plotly.js";

/* eslint-disable @typescript-eslint/no-explicit-any */
const DIM_CODE: Record<string, number> = { pass: 1, fragile: 0.5, warning: 0.5, fail: 0, not_computed: NaN };

function Ridge({ ridge }: { ridge: any }) {
  const t = useVizTokens();
  const rs = ridge.r.filter((_: number, i: number) => i % 2 === 0);
  const data: Data[] = rs.map((r: number, k: number) => {
    const i = ridge.r.indexOf(r);
    const h = ridge.hist[i] ?? [];
    const tot = Math.max(h.reduce((a: number, b: number) => a + b, 0), 1);
    return { type: "scatter", mode: "lines", x: ridge.b, y: h.map((v: number) => k * 0.6 + (v / tot) * 2), fill: "tonexty", name: pct(r, 2),
      line: { color: t.series[0], width: 1 }, fillcolor: t.series[0] + "30", hovertemplate: "r " + pct(r, 2) + "<br>b_min %{x:.0%}<br>unidentified " + pct(ridge.share_unidentified[i], 0) + "<extra></extra>" } as Data;
  });
  return <Plot height={380} data={data} layout={{ showlegend: false, hovermode: "closest", xaxis: { title: { text: "b_min across bootstrap re-estimations" }, tickformat: ".0%" },
    yaxis: { tickvals: rs.map((_: number, k: number) => k * 0.6), ticktext: rs.map((r: number, k: number) => pct(r, 2) + " (" + pct(ridge.share_unidentified[ridge.r.indexOf(r)], 0) + " unid.)" + (k < 0 ? "" : "")), title: { text: "withdrawal rate" } } }} />;
}

function Body({ env }: { env: any }) {
  const r = env.results;
  const runId = env.run_id as string;
  const hs = r.hypotheses as any[];
  return (
    <div className="space-y-4">
      <Sec id="hypotheses">
      <Viz id="RS-01" title="Hypothesis registry (H1–H12)" question="Pre-registered claims, test statistics, effect sizes, CIs, Holm/BH-adjusted p-values, data windows and verdicts — computed from persisted runs only." runId={runId} cls="model_generated" block="hypotheses"
        definition={r.preregistration.family + ". Registered " + r.preregistration.registered + ". " + r.preregistration.rules.join("; ")}>
        <DataTable rows={hs} columns={[{ key: "id", label: "ID" }, { key: "claim", label: "claim" }, { key: "statistic", label: "test statistic" },
          { key: "estimate", label: "effect", fmt: (v) => (v === null || v === undefined ? "–" : Math.abs(v) > 50 ? Math.round(v).toLocaleString() : v.toFixed(4)) },
          { key: "ci", label: "95% CI", fmt: (v) => (v ? v.map((x: number) => (Math.abs(x) > 50 ? Math.round(x).toLocaleString() : x.toFixed(4))).join(" … ") : "–") },
          { key: "p_holm", label: "p (Holm)", fmt: (v) => (v === undefined || v === null ? "–" : v < 1e-3 ? v.toExponential(1) : v.toFixed(3)) },
          { key: "p_bh", label: "p (BH)", fmt: (v) => (v === undefined || v === null ? "–" : v < 1e-3 ? v.toExponential(1) : v.toFixed(3)) },
          { key: "data_window", label: "data window", fmt: (v) => (v ? v.join("→") : "–") }, { key: "verdict", label: "verdict", fmt: (v) => <GradeTag grade={v} /> },
          { key: "evidence_grade", label: "grade", fmt: (v) => <GradeTag grade={v} /> }, { key: "run_id", label: "run", fmt: (v) => (v ? <a className="font-mono underline" href={"/runs?id=" + v}>{v.slice(0, 8)}</a> : "–") },
          { key: "note", label: "note" }]} />
      </Viz>
      </Sec>
      <Sec id="hypotheses"><Grid>
        <Viz id="RS-02" title="Evidence heatmap" question="H1–H12 × Monte Carlo / parameter / model / historical / OOS / source quality. Blank = not computed (never coloured as a fail)." runId={runId} cls="model_generated"
          definition="1 = pass, 0.5 = fragile/warning, 0 = fail. Source quality fails when the inputs are model-generated returns (public mode).">
          <Heat x={r.dimensions} y={r.evidence_matrix.map((e: any) => e.id)} z={r.evidence_matrix.map((e: any) => r.dimensions.map((d: string) => {
            const v = DIM_CODE[e[d]]; return Number.isNaN(v) ? null : v; }))} xTitle="dimension" yTitle="hypothesis" zTitle="status" zfmt=".1f" zmin={0} zmax={1} text={false}
            mask={r.evidence_matrix.map((e: any) => r.dimensions.map((d: string) => e[d] === "not_computed"))} />
        </Viz>
      </Grid></Sec>
      <Sec id="uncertainty"><Grid>
        <Viz id="RS-03" title="Monte Carlo convergence" question={"Estimate and Wilson CI width as paths increase (" + r.convergence.policy + "); automatic stop at ±" + r.convergence.precision_target_pp + "pp."} runId={runId} cls="model_generated"
          definition={r.convergence.rule + ". Stop at: " + (r.convergence.stop_at ?? "not reached")}>
          <Lines xTitle="paths" yTitle="P(success)" yfmt=".1%" xType="linear" lines={[{ name: "estimate", x: r.convergence.rows.map((x: any) => x.n_paths), y: r.convergence.rows.map((x: any) => x.p_success),
            lo: r.convergence.rows.map((x: any) => x.lo), hi: r.convergence.rows.map((x: any) => x.hi), mode: "lines+markers" }]}
            shapes={r.convergence.stop_at ? [{ type: "line", x0: r.convergence.stop_at, x1: r.convergence.stop_at, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", width: 1, color: "#888" } }] : []} />
          <Lines height={180} xTitle="paths" yTitle="CI half-width (pp)" yfmt=".2f" lines={[{ name: "half width", x: r.convergence.rows.map((x: any) => x.n_paths), y: r.convergence.rows.map((x: any) => x.half_width_pp), mode: "lines+markers" }]} />
        </Viz>
        <Viz id="RS-04" title="Threshold replication ridge" question="Distribution of the estimated b_min across joint bootstrap re-estimations, with the unidentified (no feasible allocation) frequency." runId={runId} cls="model_generated"
          empty={r.threshold_ridge ? null : "Needs a completed bond-frontier study."} definition={"Surface key " + (r.threshold_ridge?.key ?? "") + " (horizon|target)."}>
          {r.threshold_ridge ? <Ridge ridge={r.threshold_ridge} /> : null}
        </Viz>
        <Viz id="RS-06" title="Parameter and generator disagreement forest" question="Threshold (b_min at 5%) by target/horizon/generator/window/γ, and the focus policy's ΔCE across generators and windows." runId={runId} cls="model_generated">
          {r.disagreement.frontier_forest ? <Forest xTitle="b_min / CE-optimal b" xfmt=".0%" ref={null} rows={r.disagreement.frontier_forest.map((f: any) => ({ label: f.dimension + ": " + f.label, est: f.b_min, lo: f.lo, hi: f.hi, note: (f.status ?? "").replace(/_/g, " ") }))} /> : null}
          {r.disagreement.compare_robustness ? <Forest xTitle="ΔCE (compare study)" xfmt="+.1%" rows={r.disagreement.compare_robustness.map((x: any) => ({ label: x.label, est: x.error ? null : x.delta, lo: x.lo, hi: x.hi, note: x.error }))} /> : null}
        </Viz>
        <Viz id="RS-07" title="Return-order permutation distribution" question={"Worst historical cohort (" + (r.permutation.cohort_start ?? "–") + ") vs " + "permutations of the same monthly returns."} runId={runId} cls="illustrative" definition={r.permutation.flag}>
          <SampleHist xTitle="terminal real wealth (permuted orders)" xfmt="$,.0f" values={r.permutation.perm_terminal_sample} marker={r.permutation.actual_terminal} markerLabel="actual order" />
          <div className="text-xs">Actual terminal {"$" + Math.round(r.permutation.actual_terminal).toLocaleString()} sits at the {pct(r.permutation.rank_percentile, 0)} percentile of the permutation distribution; permuted shortfall rate {pct(r.permutation.perm_shortfall_rate)}; actual cohort {r.permutation.actual_shortfall ? "had" : "had no"} shortfall.</div>
        </Viz>
      </Grid></Sec>
      <Sec id="oos"><Grid>
        <Viz id="RS-05" title="Walk-forward scoreboard" question="Chronological OOS: fit before the split, select the equity share, score on later actual cohorts; regret vs the ex-post best." runId={runId} cls="observed">
          <DataTable rows={r.walk_forward} columns={[{ key: "train", label: "train", fmt: (v) => (v ? v.join("→") : "–") }, { key: "test_start", label: "test from" }, { key: "n_test_cohorts", label: "test cohorts" },
            { key: "selected_equity", label: "selected equity", fmt: (v) => pct(v, 0) }, { key: "held_out_ce", label: "held-out CE", fmt: (v) => (v ? "$" + Math.round(v).toLocaleString() : "–") },
            { key: "delta_vs_6040", label: "Δ vs 60/40", fmt: (v) => (v === undefined ? "–" : (v * 100).toFixed(2) + "%") }, { key: "ex_post_best_equity", label: "ex-post best", fmt: (v) => pct(v, 0) },
            { key: "regret", label: "regret", fmt: (v) => pct(v, 2) }, { key: "uncertainty", label: "uncertainty" }, { key: "error", label: "error" }]} />
        </Viz>
        <Viz id="RS-09" title="Bias / leakage checklist" question="Automated look-ahead, oracle, PIT-release, survivorship and distribution-assumption checks (executed in this run)." runId={runId} cls="observed">
          <DataTable rows={r.leakage} columns={[{ key: "status", label: "status", fmt: (v) => <GradeTag grade={v === "pass" ? "supported" : v === "fail" ? "invalid" : "fragile"} /> }, { key: "check", label: "check" }, { key: "detail", label: "detail" }]} />
        </Viz>
      </Grid></Sec>
      <Sec id="data-quality"><Grid>
        <Viz id="RS-08" title="Source and calendar coverage audit" question="Per-series availability, missing months, content hashes; per-universe windows and dropped months; catalog SHA." runId={runId} cls="observed"
          definition={"catalog " + r.coverage.catalog_hash + " · engine " + r.coverage.engine_version}>
          <DataTable rows={Object.entries(r.coverage.universes).map(([k, v]: any) => ({ u: k, ...v }))} columns={[{ key: "u", label: "universe" }, { key: "window", label: "window", fmt: (v) => (v ? v.join("→") : "–") },
            { key: "dropped_months", label: "dropped" }, { key: "assets", label: "assets", fmt: (v) => (v ? v.join(", ") : "–") }, { key: "error", label: "status", fmt: (v) => v ?? "ok" }]} />
          <div className="mt-2 max-h-64 overflow-auto"><DataTable rows={r.coverage.series} columns={[{ key: "series_id", label: "series" }, { key: "provenance", label: "provenance" }, { key: "first_obs", label: "first" },
            { key: "last_obs", label: "last" }, { key: "n_missing", label: "missing" }, { key: "content_hash", label: "hash" }, { key: "licence_class", label: "licence" }]} /></div>
        </Viz>
      </Grid></Sec>
      <Sec id="conclusions">
      <Viz id="RS-10" title="Research conclusion builder" question="Verified numeric claims, run IDs and caveats pulled automatically into a reproducible report — no generative interpretation." runId={runId} cls="model_generated">
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded border border-border p-3 text-[11px] leading-relaxed">{r.conclusions_markdown}</pre>
        <a className="text-xs underline" download="lifecycle_v2_conclusions.md" href={"data:text/markdown;charset=utf-8," + encodeURIComponent(r.conclusions_markdown)}>Download markdown</a>
      </Viz>
      </Sec>
    </div>
  );
}

function Validation() {
  const runs = usePickableRuns();
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">Validate any saved experiment run: Monte Carlo convergence, parameter re-estimation, model (generator) uncertainty, sequence-risk isolation,
        calibration windows, tail coverage and historical cohort replay. Nothing runs until you press the button.</p>
      <RunValidation runs={runs} />
    </div>
  );
}

const STUDY = ["hypotheses", "uncertainty", "oos", "data-quality", "conclusions"];

/** Research & Evidence: hypotheses (H1–H12 and the original H1–H4), validation, uncertainty, OOS, data quality, conclusions. */
export function Research() {
  return (
    <ResearchPage page="research" intro="The pre-registered H1–H12 family scored from persisted study runs, with multiple-testing control, evidence grades, Monte Carlo convergence, walk-forward OOS, permutation tests and automated leakage checks — plus the original H1–H4 tests and per-run validation. Negative findings carry the same weight as positive ones.">
      <Sec id={STUDY}>
        <StudyGate kind="evidence" title="Evidence study" description="Reads the latest completed studies (frontier, signed flow, PP, rebalancing, optimise, compare) and runs walk-forward, convergence, permutation and leakage checks. Run it after the other studies.">
          {(env) => <Body env={env} />}
        </StudyGate>
      </Sec>
      <Sec id="hypotheses">
        <h2 className="mt-6 text-base font-semibold">Original hypotheses H1–H4 (sweep, attribution and DP runs)</h2>
        <HypothesisTests />
      </Sec>
      <Sec id="validation"><Validation /></Sec>
    </ResearchPage>
  );
}
