"use client";
import { useState } from "react";
import { ContextBar, DataTable, Grid, Seg, StudyGate, Viz, Warnings, dataClassOf } from "@/components/research/kit";
import { Bars, Forest, Scatter, pct, spct, useAssetColor, usd } from "@/components/visualizations/charts";
import { useCatalog } from "@/lib/api/hooks";

/* eslint-disable @typescript-eslint/no-explicit-any */
const FAMILY_ORDER = ["static", "regime", "trend", "risk", "utility"];
const TIERS: Record<string, { label: string; sleeves: string[] }> = {
  multi_asset_public: { label: "Public tier", sleeves: ["us_eq", "intl_eq", "em_eq", "ust_10y", "ust_30y", "ig_credit", "fx_basket", "tbill"] },
  multi_asset_full: { label: "Full tier (WRDS)", sleeves: ["us_eq", "intl_eq", "em_eq", "ust_10y", "ust_30y", "tips", "ig_credit", "hy_credit", "gold", "commodities", "fx_basket", "tbill"] },
};
const BLOCK: Record<string, string> = { equity: "growth", rates: "duration", credit: "credit", currency: "real & currency", commodities: "real & currency", real_assets: "real & currency", cash: "cash" };

function Header({ r, runId }: { r: any; runId: string }) {
  return (
    <>
      <ContextBar items={[["Universe", r.universe.name], ["Window", r.universe.window.join(" → ")], ["Generator", r.scenario.generator], ["Paths", r.n_paths + " test / disjoint training"],
        ["Withdrawal", pct(r.withdrawal)], ["Benchmark", r.benchmark], ["Horizon", r.horizon_years + "y"], ["Run", runId.slice(0, 10)]]} />
      <Warnings items={r.warnings} />
      {Object.keys(r.unavailable ?? {}).length ? <div className="mb-3 rounded-lg border border-border p-3 text-xs"><b>Not evaluated</b> (never proxied):
        <ul className="mt-1 list-disc pl-5">{Object.entries(r.unavailable).map(([k, v]: any) => <li key={k}><code>{k}</code>: {v}</li>)}</ul></div> : null}
    </>
  );
}

/** MA-01: what each data tier contains (from the catalog; no run needed). */
function Coverage() {
  const cat = useCatalog();
  const series: any[] = cat.data?.series ?? [];
  const by = Object.fromEntries(series.map((s) => [s.series_id, s]));
  const rows = Object.entries(TIERS).flatMap(([tier, t]) => t.sleeves.map((sid) => {
    const s = by[sid];
    return { tier: t.label, sleeve: sid, label: s?.label ?? sid, cls: s?.asset_class ?? "–", block: BLOCK[s?.asset_class] ?? "–",
      provenance: s ? s.provenance : "not ingested", source: s?.source ?? (tier === "multi_asset_full" ? "WRDS CRSP (run make ingest-wrds)" : "–"),
      first: s?.first_obs?.slice(0, 10) ?? "–", last: s?.last_obs?.slice(0, 10) ?? "–" };
  }));
  const missingFull = TIERS.multi_asset_full.sleeves.filter((sid) => !by[sid]);
  return (
    <Viz id="MA-01" cls="observed" empty={cat.isError ? "API unreachable: start it with make api." : null}
      footnote={missingFull.length ? "Full tier unavailable here: " + missingFull.join(", ") + " not ingested (WRDS)." : "Both tiers available."}>
      <div className="max-h-96 overflow-auto">
        <DataTable rows={rows} columns={[{ key: "tier", label: "tier" }, { key: "sleeve", label: "sleeve" }, { key: "label", label: "description" },
          { key: "cls", label: "asset class" }, { key: "block", label: "block" }, { key: "provenance", label: "provenance" }, { key: "source", label: "source" },
          { key: "first", label: "first" }, { key: "last", label: "last" }]} />
      </div>
    </Viz>
  );
}

function StaticBody({ env }: { env: any }) {
  const r = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(r);
  const color = useAssetColor();
  const statics = Object.keys(r.static_weights).filter((k) => k !== "crra_static");
  const rows = r.scorecard.filter((s: any) => s.family === "static");
  return (
    <div className="space-y-4">
      <Header r={r} runId={runId} />
      <Grid>
        <Viz id="MA-02" runId={runId} cls={cls} block="static_weights"
          table={() => <DataTable rows={statics.map((k) => ({ policy: k, ...r.static_weights[k] }))} columns={[{ key: "policy", label: "policy" },
            ...r.assets.map((a: string) => ({ key: a, label: a, fmt: (v: any) => pct(v, 1) }))]} />}>
          <Bars stacked xTitle="policy" yTitle="target weight" yfmt=".0%" x={statics}
            series={r.assets.map((a: string, i: number) => ({ name: a, color: color(a, i), y: statics.map((k) => r.static_weights[k][a] ?? 0) }))} />
        </Viz>
        <Viz id="MA-03" runId={runId} cls={cls} block="scorecard">
          <DataTable rows={rows.map((s: any) => ({ ...s, d: s.delta_ce?.delta, lo: s.delta_ce?.lo, hi: s.delta_ce?.hi }))} columns={[
            { key: "label", label: "policy" }, { key: "ce", label: "CE", fmt: usd }, { key: "d", label: "ΔCE vs 60/40", fmt: (v) => (v === undefined ? "benchmark" : spct(v)) },
            { key: "lo", label: "95% CI", fmt: (v, row) => (v === undefined ? "–" : spct(v) + " / " + spct(row.hi)) }, { key: "success", label: "P(success)", fmt: (v) => pct(v) },
            { key: "mdd_median", label: "median MDD", fmt: (v) => pct(v) }, { key: "turnover_yr", label: "turnover/yr", fmt: (v) => v.toFixed(2) }]} />
          <p className="mt-2 text-[11px] text-muted-foreground">{r.definitions.ce}.</p>
        </Viz>
      </Grid>
    </div>
  );
}

function DynamicBody({ env }: { env: any }) {
  const r = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(r);
  const color = useAssetColor();
  const score: any[] = [...r.scorecard].sort((a, b) => FAMILY_ORDER.indexOf(a.family) - FAMILY_ORDER.indexOf(b.family));
  const dynamic = r.policies.map((p: any) => p.policy).filter((p: string) => r.weights_by_year[p]?.length);
  const [sel, setSel] = useState<string>(dynamic.includes("trend_tsmom") ? "trend_tsmom" : dynamic[0]);
  const wby: number[][] = r.weights_by_year[sel] ?? [];
  const famColor = (f: string) => color(f, FAMILY_ORDER.indexOf(f));
  const reg = r.fit?.regime_blocks;
  const saver = Object.fromEntries((r.saver ?? []).map((s: any) => [s.policy, s]));
  const others = score.filter((s) => s.policy !== r.benchmark);
  return (
    <div className="space-y-4">
      <Header r={r} runId={runId} />
      <Grid>
        <Viz id="MA-04" runId={runId} cls={cls} block="scorecard">
          <Forest xTitle={"ΔCE vs " + r.benchmark} xfmt="+.0%" refLabel="no difference"
            rows={others.map((s) => ({ label: s.family + " · " + s.label, est: s.delta_ce?.delta ?? null, lo: s.delta_ce?.lo, hi: s.delta_ce?.hi }))} />
          <p className="mt-1 text-[11px] text-muted-foreground">Fitted on training paths: CRRA static blocks {JSON.stringify(r.fit?.crra_static_blocks ?? {})}; parametric tilts {JSON.stringify(r.fit?.theta ?? {})}.</p>
        </Viz>
        <Viz id="MA-05" runId={runId} cls={cls}>
          <Scatter xTitle={"P(failure, " + r.horizon_years + "y)"} yTitle="CE (real $/yr)" xfmt=".0%" yfmt="$,.0f"
            pts={FAMILY_ORDER.filter((f) => score.some((s) => s.family === f)).map((f) => {
              const g = score.filter((s) => s.family === f);
              return { name: f, color: famColor(f), x: g.map((s) => 1 - s.success), y: g.map((s) => s.ce), text: g.map((s) => s.label), size: 10 };
            })} />
        </Viz>
        <Viz id="MA-06" runId={runId} cls={cls} selection={{ policy: sel }}
          table={() => <DataTable rows={wby.map((row, i) => ({ year: i, ...Object.fromEntries(r.assets.map((a: string, j: number) => [a, row[j]])) }))}
            columns={[{ key: "year", label: "year" }, ...r.assets.map((a: string) => ({ key: a, label: a, fmt: (v: any) => pct(v, 1) }))]} />}>
          <div className="mb-2"><Seg label="Policy" value={sel} onChange={setSel} options={dynamic.map((p: string) => ({ value: p, label: p }))} /></div>
          <Bars stacked height={360} xTitle="years since retirement" yTitle="average weight" yfmt=".0%" x={wby.map((_, i) => i)}
            series={r.assets.map((a: string, j: number) => ({ name: a, color: color(a, j), y: wby.map((row) => row[j]) }))} />
        </Viz>
        <Viz id="MA-07" runId={runId} cls={cls} empty={reg ? null : (r.unavailable?.regime_blocks ?? "Regime policy not evaluated in this run.")}>
          {reg ? <>
            <Bars stacked xTitle="point-in-time regime" yTitle="block weight" yfmt=".0%" x={Object.keys(reg.per_regime_blocks).map((k) => "regime " + k)}
              series={r.blocks.map((b: string, i: number) => ({ name: b, color: color(b, i), y: Object.values(reg.per_regime_blocks).map((m: any) => m[b] ?? 0) }))} />
            <div className="mt-1 text-[11px] text-muted-foreground">Signal: {reg.signal?.signal ?? "filtered, lagged"}. Starting paths per regime: {(r.by_regime ?? []).map((b: any) => "regime " + b.regime + " n=" + b.n + (b.note ? " (" + b.note + ")" : b.regime_blocks ? " ΔCE " + spct(b.regime_blocks.delta) : "")).join(" · ")}</div>
          </> : null}
        </Viz>
        <Viz id="MA-08" runId={runId} cls={cls}>
          <Scatter xTitle="turnover per year (one-way)" yTitle="ΔCE vs 60/40" xfmt=".2f" yfmt="+.0%"
            pts={FAMILY_ORDER.filter((f) => others.some((s) => s.family === f)).map((f) => {
              const g = others.filter((s) => s.family === f);
              return { name: f, color: famColor(f), x: g.map((s) => s.turnover_yr), y: g.map((s) => s.delta_ce?.delta ?? 0), text: g.map((s) => s.label), size: 10 };
            })} />
        </Viz>
        <Viz id="MA-09" runId={runId} cls={cls} footnote={r.definitions.saver}>
          <Bars xTitle="policy" yTitle="ΔCE vs 60/40" yfmt="+.0%" x={others.map((s) => s.policy)} series={[
            { name: "retiree", y: others.map((s) => s.delta_ce?.delta ?? null) },
            { name: "saver", y: others.map((s) => saver[s.policy]?.delta_ce?.delta ?? null) }]} />
        </Viz>
        <Viz id="MA-10" runId={runId} cls={cls} empty={(r.robustness ?? []).length ? null : "No robustness generators in this run's spec."}>
          <Forest xTitle="ΔCE vs 60/40" xfmt="+.0%" refLabel="no difference" rows={[
            ...others.map((s) => ({ label: s.policy + " · " + r.scenario.generator, est: s.delta_ce?.delta ?? null, lo: s.delta_ce?.lo, hi: s.delta_ce?.hi })),
            ...(r.robustness ?? []).map((x: any) => ({ label: (x.policy ?? "–") + " · " + x.generator, est: x.error ? null : x.delta, lo: x.lo, hi: x.hi, note: x.error }))]} />
        </Viz>
      </Grid>
    </div>
  );
}

const DESC = "Ten policies across five families on the multi-asset universe (public tier by default; switch to multi_asset_full after the WRDS ingest), "
  + "fitted on training paths and scored on disjoint test paths for a retiree and a saver (~1 minute).";

/** Permanent Portfolio › Multi-Asset All-Weather. */
export function MultiAssetAllWeather() {
  return (
    <div className="space-y-4">
      <Coverage />
      <StudyGate kind="multi_asset" title="Multi-asset allocation study" description={DESC}>{(env) => <StaticBody env={env} />}</StudyGate>
    </div>
  );
}

/** Portfolio Optimization › Dynamic Multi-Asset Allocation. */
export function DynamicMultiAsset() {
  return <StudyGate kind="multi_asset" title="Multi-asset allocation study" description={DESC}>{(env) => <DynamicBody env={env} />}</StudyGate>;
}
