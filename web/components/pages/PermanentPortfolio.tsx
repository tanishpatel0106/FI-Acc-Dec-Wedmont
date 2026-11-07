"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ResearchPage, Sec } from "@/components/research/page";
import { useResearchContext } from "@/lib/store";
import { ContextBar, DataTable, Empty, Grid, Kpi, Seg, StudyGate, Viz, Warnings, dataClassOf } from "@/components/research/kit";
import { Bars, Forest, Heat, Lines, Scatter, Ternary, ci, pct, spct, useAssetColor, usd } from "@/components/visualizations/charts";
import { apiPost } from "@/lib/api/client";
import { useTrace } from "@/lib/api/v2";

/* eslint-disable @typescript-eslint/no-explicit-any */
function GoldStatus() {
  const q = useQuery({ queryKey: ["pp-gold-default"], queryFn: () => apiPost<any>("/v1/studies/permanent", {}, { submit: "false" }) });
  const d = q.data;
  if (!d) return null;
  if (d.status === "done") return null;
  return (
    <div className="mb-4 rounded-lg border border-[var(--viz-s4)]/50 bg-[var(--viz-s4)]/5 p-3 text-xs">
      <b>Classic Permanent Portfolio with gold (universe pp_modern_etf): {d.status === "none" ? "not run" : d.status}.</b>{" "}
      {d.status === "failed" ? <span>{String(d.error ?? "").split("\n")[0]}. </span> : null}
      Gold enters only as an observed fund total return (WRDS CRSP GLD); no public gold history is spliced in and no zero-return stand-in is used.
      The panels below therefore show the gold-free variants on <code>core_duration</code> where noted. Ingest WRDS (<code>make ingest-wrds</code>) and re-run to populate the gold sleeve.
    </div>
  );
}

function BrowneEvents({ runId, policy, res }: { runId: string; policy: string; res: any }) {
  const [path, setPath] = useState(0);
  const tr = useTrace(runId, { policy, path });
  const color = useAssetColor();
  const t = tr.data?.trace;
  if (tr.isError) return <Empty>Trace unavailable: {String((tr.error as Error).message)}</Empty>;
  if (!t) return <div className="h-72 animate-pulse rounded bg-muted/40" />;
  const months = t.monthly.reason.map((_: number, i: number) => i / 12);
  const checks = months.filter((_: number, i: number) => i % 12 === 0 && i > 0);
  const trades = t.monthly.reason.map((r: number, i: number) => (r === 4 ? i / 12 : null)).filter((x: number | null) => x !== null);
  const rows = t.monthly.reason.map((r: number, i: number) => ({ month: i, reason: t.reasons[r], cost: t.monthly.cost[i], funded: t.monthly.funded_draw[i],
    ...Object.fromEntries(t.assets.map((a: string, ai: number) => [a, t.monthly.trades[i][ai]])) })).filter((r: any) => r.reason !== "none");
  return (
    <>
      <div className="mb-2 flex items-center gap-2 text-xs">path <input type="number" min={0} value={path} onChange={(e) => setPath(Math.max(0, Number(e.target.value)))}
        className="h-7 w-20 rounded border border-input bg-transparent px-2" /> <span className="text-muted-foreground">policy {t.policy} · rule {t.rule} · {trades.length} band trades in {Math.round(months.length / 12)} years</span></div>
      <Lines xTitle="years since retirement" yTitle="actual sleeve weight (pre-trade)" yfmt=".0%" lines={t.assets.map((a: string, ai: number) => ({ name: a, color: color(a, ai),
        x: months, y: t.monthly.pre_weights.map((w: number[]) => w[ai]), width: 1.5 }))}
        shapes={[{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0.15, y1: 0.15, line: { dash: "dot", width: 1, color: "#888" } },
          { type: "line", xref: "paper", x0: 0, x1: 1, y0: 0.35, y1: 0.35, line: { dash: "dot", width: 1, color: "#888" } },
          ...checks.map((x: number) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 0.03, line: { width: 1, color: "#888" } })),
          ...trades.map((x: number) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 1, line: { width: 1, color: "#d95926", dash: "dash" } }))]} />
      <div className="text-[11px] text-muted-foreground">Dotted: 15% / 35% bands. Ticks: annual review dates. Dashed orange: review-date breach → all sleeves restored to target. A breach between reviews does not trade in the classic rule.</div>
      <div className="mt-2 max-h-56 overflow-auto"><DataTable rows={rows} columns={[{ key: "month", label: "month" }, { key: "reason", label: "trigger" },
        ...t.assets.map((a: string) => ({ key: a, label: a + " $", fmt: usd })), { key: "cost", label: "cost", fmt: usd }, { key: "funded", label: "funded draw", fmt: usd }]} /></div>
      {res ? null : null}
    </>
  );
}

function Body({ env }: { env: any }) {
  const res = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(res);
  const color = useAssetColor();
  const mh = String(Math.max(...res.horizons));
  const [simZ, setSimZ] = useState<"ce" | "success">("ce");
  const score = res.scorecard as any[];
  const shap = res.shapley;
  return (
    <div className="space-y-4">
      <ContextBar items={[["Universe", res.universe.name], ["Window", res.universe.window.join(" → ")], ["Generator", res.scenario.generator], ["Paths", res.n_paths],
        ["Withdrawal", pct(res.withdrawal)], ["Benchmark", res.benchmark], ["Costs", res.costs.commission_bps + "+" + res.costs.half_spread_bps + " bps"],
        ["Reference PP", res.reference_pp ?? "–"], ["Run", runId.slice(0, 10)]]} />
      <Warnings items={[...res.warnings, res.sample_note]} />
      {Object.keys(res.unavailable).length ? <div className="rounded-lg border border-border p-3 text-xs"><b>Unavailable policies on this universe</b> (excluded, never proxied):
        <ul className="mt-1 list-disc pl-5">{Object.entries(res.unavailable).map(([k, v]: any) => <li key={k}><code>{k}</code>: {v}</li>)}</ul></div> : null}
      <Sec id="overview"><CompareWith6040 score={score} benchmark={res.benchmark} /><Grid>
        <Viz id="PP-01" title="Classic four-sleeve matrix" question="Target vs actual average weight, purpose, measured risk exposure and the exact canonical source of each sleeve."
          runId={runId} cls={cls} definition="Roles are hypotheses, not guaranteed hedges. Exposures are estimated on the calibration window (real returns; inflation beta on nominal returns).">
          <DataTable rows={res.sleeves.map((s: any) => ({ ...s, vol: s.risk_exposure?.real_vol, beta: s.risk_exposure?.equity_beta, ib: s.risk_exposure?.inflation_beta_nominal,
            src: s.source ? s.source.source + " (" + s.source.provenance + ")" : s.reason }))} columns={[
            { key: "sleeve", label: "sleeve" }, { key: "asset", label: "series" }, { key: "target", label: "target", fmt: (v) => (v ? pct(v, 0) : "–") },
            { key: "actual_mean_weight", label: "actual (mean)", fmt: (v) => pct(v) }, { key: "purpose", label: "purpose" }, { key: "vol", label: "real vol", fmt: (v) => pct(v) },
            { key: "beta", label: "equity β", fmt: (v) => (v === undefined || v === null ? "–" : v.toFixed(2)) }, { key: "ib", label: "inflation β", fmt: (v) => (v === undefined || v === null ? "–" : v.toFixed(2)) },
            { key: "src", label: "canonical source" }]} />
        </Viz>
        <Viz id="PP-02" title="Policy comparison scorecard" question={"Paired comparison vs " + res.benchmark + " on one tensor (identical sample, spending, costs)."}
          runId={runId} cls={cls} block="scorecard" definition="ΔCE: paired, path-bootstrap 95% CI. Δsuccess: paired difference with normal-approximation CI. Cost: bps of average wealth per year.">
          <DataTable rows={score.map((m) => ({ ...m, ce_v: m.ce.ce, succ: m.success[mh]?.p, dce: m.delta_ce_vs_benchmark?.delta, dlo: m.delta_ce_vs_benchmark?.lo,
            dhi: m.delta_ce_vs_benchmark?.hi, dsu: m.delta_success_vs_benchmark?.diff, cv: m.severity.cvar95_unconditional }))} columns={[
            { key: "label", label: "policy" }, { key: "rebalancer", label: "rule" }, { key: "ce_v", label: "CE", fmt: usd }, { key: "dce", label: "ΔCE", fmt: (v) => spct(v) },
            { key: "dlo", label: "ΔCE CI", fmt: (v, r) => (v === undefined ? "–" : spct(v) + " / " + spct(r.dhi)) }, { key: "succ", label: "P(success " + mh + "y)", fmt: (v) => pct(v) },
            { key: "dsu", label: "Δsuccess", fmt: (v) => spct(v, 1) }, { key: "cv", label: "CVaR95 unmet", fmt: usd }, { key: "max_drawdown_median", label: "median MDD", fmt: (v) => pct(v) },
            { key: "cost_bps_per_year", label: "cost bps/yr", fmt: (v) => (v ?? 0).toFixed(2) }, { key: "turnover_one_way_per_year", label: "turnover/yr", fmt: (v) => pct(v) }]} />
        </Viz>
      </Grid></Sec>
      <Sec id="conditional"><Grid>
        <Viz id="PP-03" title="Conditional advantage heatmap" question={"Paired ΔCE of " + res.conditional.policy + " vs " + res.conditional.benchmark + " by withdrawal rate and starting regime; × = CI includes zero."}
          runId={runId} cls={cls} definition="Starting regime = filtered history label of the first sampled month (bootstrap start pool). All starts = unconditional.">
          {res.conditional.rows.length ? <Heat x={res.conditional.r} y={res.conditional.rows.map((r: any) => r.label)} z={res.conditional.rows.map((r: any) => r.delta)} diverging
            xTitle="withdrawal rate" yTitle="start" zTitle="ΔCE" zfmt=".1%" xfmt={(v) => pct(v, 0)}
            mask={res.conditional.rows.map((r: any) => r.lo.map((lo: number, i: number) => lo <= 0 && r.hi[i] >= 0))} /> : <Empty>No conditional comparison available.</Empty>}
        </Viz>
        <Viz id="PP-04" title="Macro regime quadrants" question="Empirical real returns by growth × inflation quadrant (lagged, point-in-time classification), with observation counts."
          runId={runId} cls="observed" empty={res.quadrants.available ? null : res.quadrants.reason}
          definition={(res.quadrants.method ?? "") + ". " + (res.quadrants.caveat ?? "")}>
          {res.quadrants.available ? <>
            <Bars xTitle="quadrant" yTitle="mean real return (annualised)" yfmt=".0%" x={res.quadrants.rows.map((r: any) => r.quadrant + " (n=" + r.n_months + ")")}
              series={res.universe.assets.map((a: string, ai: number) => ({ name: a, color: color(a, ai), y: res.quadrants.rows.map((r: any) => r.assets[a]?.mean_annual ?? null),
                err: [res.quadrants.rows.map((r: any) => 1.96 * (r.assets[a]?.se_annual ?? 0)), res.quadrants.rows.map((r: any) => 1.96 * (r.assets[a]?.se_annual ?? 0))] as [number[], number[]] }))} />
            <div className="text-[11px] text-muted-foreground">Window {res.quadrants.window.join(" → ")}; error bars ±1.96 SE.</div>
          </> : null}
        </Viz>
        <Viz id="PP-05" title="Dynamic PP weight river" question="How the regime-adaptive PP shifts its four sleeves as the filtered signal moves (expected weights by year)."
          runId={runId} cls={cls} empty={res.river ? null : "Dynamic PP needs a regime-bearing generator and the gold-free fallback universe still supports it; not available in this run."}
          definition="Weights per regime fitted on training paths; river = share of paths in each signal state × per-regime weights. Signal: point-in-time filtered regime, lagged one month.">
          {res.river ? <>
            <Bars stacked xTitle="year" yTitle="expected weight" yfmt=".0%" x={res.river.years}
              series={res.river.assets.map((a: string, ai: number) => ({ name: a, color: color(a, ai), y: res.river.expected_weights.map((w: number[]) => w[ai]) }))} />
            <DataTable rows={Object.entries(res.river.per_regime).map(([k, w]: any) => ({ regime: k, ...w }))} columns={[{ key: "regime", label: "regime" },
              ...res.river.assets.map((a: string) => ({ key: a, label: a, fmt: (v: number) => pct(v, 1) }))]} />
          </> : null}
        </Viz>
        <Viz id="PP-06" title="Gold marginal utility and hedge effect" question="Incremental CE of gold (PP vs PP without gold) by starting regime; downside co-loss and CPI correlation."
          runId={runId} cls={cls} empty={res.gold.available ? null : (res.gold.reason ?? "gold not in universe") + ". Requires an observed gold fund series (WRDS GLD)."}
          definition={res.gold.lag}>
          {res.gold.available ? <>
            <Forest xTitle="ΔCE from gold" xfmt=".1%" rows={res.gold.incremental_ce.map((r: any) => ({ label: r.label, est: r.delta, lo: r.lo, hi: r.hi }))} />
            <div className="grid grid-cols-3 gap-2 text-xs"><Kpi label="P(gold loss | equity worst decile)" value={pct(res.gold.p_gold_loss_given_equity_worst_decile)} sub={"unconditional " + pct(res.gold.p_gold_loss_unconditional)} />
              <Kpi label="corr(gold, CPI) high inflation" value={res.gold.corr_gold_cpi_high_inflation?.toFixed(2) ?? "–"} /><Kpi label="corr(gold, CPI) low inflation" value={res.gold.corr_gold_cpi_low_inflation?.toFixed(2) ?? "–"} sub={res.gold.n_months + " months"} /></div>
          </> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="composition"><Grid>
        <Viz id="PP-07" title="Long-bond duration replacement" question="Replace the long-Treasury sleeve with 2/5/10/30Y (cash and gold held constant): CE, success, tail shortfall, duration and DV01."
          runId={runId} cls={cls} definition="Duration/DV01 from the latest GSW curve for a par bond of that maturity; DV01 per $1m of sleeve, per 1bp. Portfolio duration = 25% × sleeve duration.">
          <Bars xTitle="sleeve maturity" yTitle="CE ($/yr)" yfmt="$,.0f" x={res.duration.filter((d: any) => d.available).map((d: any) => d.maturity + "Y")}
            series={[{ name: "CE", y: res.duration.filter((d: any) => d.available).map((d: any) => d.ce) }]} />
          <DataTable rows={res.duration} columns={[{ key: "asset", label: "sleeve" }, { key: "available", label: "available" }, { key: "success", label: "P(success)", fmt: (v) => pct(v) },
            { key: "cvar95_unmet", label: "CVaR95 unmet", fmt: usd }, { key: "modified_duration", label: "mod. duration", fmt: (v) => (v ? v.toFixed(2) : "–") },
            { key: "dv01_per_1m_sleeve", label: "DV01/$1m", fmt: usd }, { key: "portfolio_duration", label: "portfolio dur.", fmt: (v) => (v ? v.toFixed(2) : "–") }]} />
        </Viz>
        <Viz id="PP-08" title="Cash buffer trade-off" question="Years of withdrawals held in bills vs CE and first-10-year shortfall (paired against no buffer); growth sacrifice in median terminal wealth."
          runId={runId} cls={cls} empty={res.cash_buffer.length ? null : "No PP reference policy available for the buffer comparison."}>
          <Lines xTitle="reserve (years of withdrawals)" yTitle="P(shortfall in first 10y)" yfmt=".1%" lines={[{ name: "first-10y shortfall", x: res.cash_buffer.map((c: any) => c.reserve_years),
            y: res.cash_buffer.map((c: any) => c.first10y_shortfall), mode: "lines+markers" }]} />
          <DataTable rows={res.cash_buffer.map((c: any) => ({ ...c, d: c.delta_ce?.delta, lo: c.delta_ce?.lo, hi: c.delta_ce?.hi }))} columns={[{ key: "reserve_years", label: "years" },
            { key: "ce", label: "CE", fmt: usd }, { key: "d", label: "ΔCE vs 0", fmt: (v, r) => (v === undefined ? "–" : spct(v) + " [" + spct(r.lo) + ", " + spct(r.hi) + "]") },
            { key: "growth_sacrifice_median_terminal", label: "Δ median terminal", fmt: usd }]} />
        </Viz>
        <Viz id="PP-09" title="Defensive-mix simplex" question="Equity fixed at 25%; the other 75% split across long bonds, gold and cash. Masked points need data the universe lacks."
          runId={runId} cls={cls} definition="Each point is a full simulation on the shared tensor with the Browne 15/35 rule.">
          <Seg label="Colour" value={simZ} onChange={setSimZ} options={[{ value: "ce", label: "CE" }, { value: "success", label: "success" }]} />
          <Ternary a={res.simplex.map((p: any) => p.bond / 0.75)} b={res.simplex.map((p: any) => p.gold / 0.75)} c={res.simplex.map((p: any) => p.cash / 0.75)}
            z={res.simplex.map((p: any) => (p.masked ? null : p[simZ]))} masked={res.simplex.map((p: any) => p.masked)} labels={["long bond", "gold", "cash"]}
            zTitle={simZ === "ce" ? "CE $/yr" : "P(success)"} zfmt={simZ === "ce" ? "$,.0f" : ".0%"} />
        </Viz>
        <Viz id="PP-12" title="Ablation / Shapley panel" question="Incremental CE of gold, nominal duration, real duration and cash; Shapley vs stand-alone gains."
          runId={runId} cls={cls} definition={shap.baseline + ". " + shap.note}>
          <Bars xTitle="sleeve" yTitle="CE contribution ($/yr)" yfmt="$,.0f" x={shap.players} series={[
            { name: "Shapley", y: shap.players.map((p: string) => shap.shapley_ce_usd[p]) }, { name: "stand-alone", y: shap.players.map((p: string) => shap.alone[p]) }]} />
          <div className="text-xs text-muted-foreground">v(full) {usd(shap.v_full)} · v(empty, 100% equity) {usd(shap.v_empty)} · interaction (non-additivity) {usd(shap.interaction)}</div>
        </Viz>
      </Grid>
      {res.robust ? <Viz id="PP-robust" title="Robust PP (minimax regret across generators)" question="Candidate defensive mixes and their worst-case regret." runId={runId} cls={cls}>
        <Scatter xTitle="candidate" yTitle="max regret" yfmt=".1%" pts={[{ name: "max regret", x: res.robust.candidates.map((_: any, i: number) => i), y: res.robust.max_regret,
          text: res.robust.candidates.map((c: number[]) => "bond " + pct(c[0], 1) + " gold " + pct(c[1], 1) + " cash " + pct(c[2], 1)) }]} />
        <div className="text-xs text-muted-foreground">chosen: bond {pct(res.robust.chosen[0], 1)}, gold {pct(res.robust.chosen[1], 1)}, cash {pct(res.robust.chosen[2], 1)} · {ci(null, null)}</div>
      </Viz> : null}
      </Sec>
      <Sec id="history"><Grid>
        <Viz id="PP-10" title="Browne band rule events" question="Monthly sleeve weights, annual monitoring checks, 15/35 breaches and the restoring trades on one path."
          runId={runId} cls={cls} definition="Classic rule: check once a year; if any sleeve < 15% or > 35%, trade all sleeves back to target. Monitoring monthly is a different strategy (pp_15_35_monthly).">
          <BrowneEvents runId={runId} policy={res.reference_pp ?? "pp_classic"} res={null} />
        </Viz>
        <Viz id="PP-11" title="Historical cohort PP race" question={"Relative real terminal wealth vs " + res.benchmark + " across actual starting cohorts (" + (res.cohorts.years ?? "") + "-year windows)."}
          runId={runId} cls="observed" empty={res.cohorts.available ? null : res.cohorts.reason} definition={res.cohorts.caveat}>
          {res.cohorts.available ? <Lines xTitle="cohort start" yTitle="terminal wealth / benchmark" yfmt=".2f" xType="date"
            lines={Object.entries(res.cohorts.policies).filter(([k]) => k !== res.benchmark).map(([k, v]: any) => ({ name: k, x: res.cohorts.starts, y: v.relative_terminal }))}
            shapes={[{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 1, y1: 1, line: { dash: "dot", width: 1, color: "#888" } }]} /> : null}
        </Viz>
      </Grid></Sec>
    </div>
  );
}

/** Map Permanent Portfolio study policies onto the policy set of the Strategy Comparison study. */
const TO_COMPARE: Record<string, string | null> = { sixty_forty: "sixty_forty", pp_no_gold: "pp_ex_gold" };

/** "Compare with 60/40": carries the selected policies into Strategy Comparison through the shared context and URL. */
function CompareWith6040({ score, benchmark }: { score: any[]; benchmark: string }) {
  const router = useRouter();
  const setCtx = useResearchContext((c) => c.set);
  const names = score.map((r: any) => r.policy as string).filter((p) => p !== benchmark);
  const [picked, setPicked] = useState<string[]>(names.slice(0, 3));
  const mapped = picked.map((p) => TO_COMPARE[p] ?? null).filter((x): x is string => !!x);
  const inStudyOnly = picked.filter((p) => !TO_COMPARE[p]);
  function go() {
    const policies = [...new Set(["sixty_forty", ...mapped, "all_equity", "forty_sixty"])];
    const focus = mapped[0] ?? "pp_ex_gold";
    setCtx({ comparePolicies: policies.join(","), compareFocus: focus });
    router.push("/compare?section=policies&policies=" + policies.join(",") + "&focus=" + focus + "&from=permanent&pp=" + picked.join(","));
  }
  return (
    <div className="rounded-lg border border-border p-3 text-xs" data-testid="compare-with-6040">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-medium">Compare with 60/40</div>
        <button onClick={go} className="rounded border border-border px-3 py-1 hover:bg-muted">Open in Strategy Comparison →</button>
      </div>
      <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Policies to carry into the comparison">
        {names.map((n) => (
          <label key={n} className="flex items-center gap-1 rounded border border-border px-2 py-0.5">
            <input type="checkbox" checked={picked.includes(n)} onChange={(e) => setPicked(e.target.checked ? [...picked, n] : picked.filter((x) => x !== n))} />{n}
          </label>
        ))}
      </div>
      <p className="mt-2 text-muted-foreground">
        The comparison study runs on a universe without gold, so only gold-free equivalents carry over ({mapped.length ? mapped.join(", ") : "none selected"}).
        {inStudyOnly.length ? <> {inStudyOnly.join(", ")} {inStudyOnly.length > 1 ? "are" : "is"} compared against {benchmark} here, on the PP study&apos;s matched sample (PP-02).</> : null}
        {" "}<Link className="underline" href="/methodology?section=data">Why gold needs WRDS</Link>
      </p>
    </div>
  );
}

/** Permanent Portfolio: classic four-sleeve policy, conditional advantage, composition, and history. */
export function PermanentPortfolio() {
  return (
    <ResearchPage page="permanent" intro="Classic Browne 25/25/25/25 (stocks, long Treasuries, gold, T-bills) with the annual 15/35 review, against 60/40, best static, duration and TIPS variants, ablations and regime-adaptive and robust versions — on one shared, matched sample.">
      <GoldStatus />
      <StudyGate kind="permanent" title="Permanent Portfolio study" description="Default universe pp_modern_etf needs an observed gold series (WRDS GLD). Without WRDS, edit the spec to universe core_duration for the gold-free ablations.">
        {(env) => <Body env={env} />}
      </StudyGate>
    </ResearchPage>
  );
}
