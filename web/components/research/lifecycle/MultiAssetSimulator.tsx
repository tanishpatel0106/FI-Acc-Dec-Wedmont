"use client";
import { useState } from "react";
import type { Data } from "plotly.js";
import { DataTable, Grid, StudyGate, Viz, Warnings, ContextBar } from "@/components/research/kit";
import { Plot, useVizTokens } from "@/components/visualizations/Plot";
import { pct, usd, useAssetColor } from "@/components/visualizations/charts";

/* eslint-disable @typescript-eslint/no-explicit-any */
const POLICY_LABELS: Record<string, string> = {
  pp_lifecycle: "Lifecycle Permanent Portfolio", lifecycle_adaptive: "Lifecycle-adaptive", target_date: "Target-date glidepath",
  sixty_forty: "Static 60/40", pp_multi_asset: "Multi-asset all-weather", pp_classic: "Classic Permanent Portfolio",
  risk_parity: "Risk parity", trend_tsmom: "Trend", inverse_vol: "Inverse volatility", vol_target: "Vol-targeted 60/40",
  regime_adaptive: "Regime-adaptive", crra_parametric: "CRRA parametric",
};

/** Investor + start-date assumptions shared by the replay and the multi-asset simulator. */
export function InvestorStartForm({ shown, onRun, kind }: { shown: any; onRun: (spec: any) => void; kind: "historical_replay" | "lifecycle_sim" }) {
  const inv = shown?.investor ?? {};
  const [f, setF] = useState({
    start: shown?.start ?? "2007-01", start_age: inv.start_age ?? 20, initial_wealth: inv.initial_wealth ?? 10000, salary: inv.salary ?? 45000,
    savings_rate: inv.savings_rate ?? 0.15, retirement_age: inv.retirement_age ?? 65, spending_ratio: inv.spending_ratio ?? 0.7,
    pension_ratio: inv.pension_ratio ?? 0.3, gamma: shown?.preferences?.gamma ?? 4, universe_mode: shown?.universe_mode ?? "fixed",
    rebalance: shown?.rebalance?.mode ?? "absolute_band", scenario_source: shown?.scenario_source ?? "simulated_from_start",
    n_paths: shown?.n_paths ?? 1000, policies: (shown?.policies ?? ["pp_lifecycle", "lifecycle_adaptive", "target_date", "sixty_forty"]) as string[],
    experiments: shown?.experiments ?? false,
  });
  const num = (k: string, step = 1, label = k) => (
    <label className="flex flex-col gap-0.5"><span className="text-muted-foreground">{label}</span>
      <input aria-label={label} type="number" step={step} value={(f as any)[k]} onChange={(e) => setF({ ...f, [k]: Number(e.target.value) })}
        className="h-8 w-28 rounded border border-input bg-transparent px-2" /></label>
  );
  function submit() {
    const investor = { start_age: f.start_age, initial_wealth: f.initial_wealth, salary: f.salary, savings_rate: f.savings_rate,
      retirement_age: f.retirement_age, spending_ratio: f.spending_ratio, pension_ratio: f.pension_ratio };
    const common = { start: f.start, investor, preferences: { gamma: f.gamma, beta_annual: 0.97 }, universe_mode: f.universe_mode,
      rebalance: { mode: f.rebalance, band: 0.05, cadence_months: 12, funding: "cash_flow_targeting" } };
    onRun(kind === "lifecycle_sim" ? { ...common, scenario_source: f.scenario_source, n_paths: f.n_paths, policies: f.policies }
      : { ...common, experiments: f.experiments, forward_paths: Math.min(f.n_paths, 1000) });
  }
  return (
    <div className="rounded-lg border border-border p-3 text-xs" data-testid={kind + "-form"}>
      <div className="mb-2 font-medium">Investor and start date</div>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-0.5"><span className="text-muted-foreground">start (year-month)</span>
          <input aria-label="start month" type="month" min="1996-01" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })}
            className="h-8 rounded border border-input bg-transparent px-2" /></label>
        {num("start_age", 1, "age at start")}{num("initial_wealth", 1000, "initial wealth $")}{num("salary", 1000, "salary $/yr")}
        {num("savings_rate", 0.01, "savings rate")}{num("retirement_age", 1, "retirement age")}{num("spending_ratio", 0.05, "spending / final salary")}
        {num("pension_ratio", 0.05, "pension / final salary")}{num("gamma", 0.5, "risk aversion γ")}
        <label className="flex flex-col gap-0.5"><span className="text-muted-foreground">universe</span>
          <select aria-label="universe mode" value={f.universe_mode} onChange={(e) => setF({ ...f, universe_mode: e.target.value })} className="h-8 rounded border border-input bg-transparent px-1">
            <option value="fixed">fixed (comparable)</option><option value="expanding">expanding (sleeves join when eligible)</option></select></label>
        <label className="flex flex-col gap-0.5"><span className="text-muted-foreground">rebalancing</span>
          <select aria-label="rebalancing" value={f.rebalance} onChange={(e) => setF({ ...f, rebalance: e.target.value })} className="h-8 rounded border border-input bg-transparent px-1">
            <option value="absolute_band">5-point bands, monthly check</option><option value="calendar">annual calendar</option></select></label>
        {kind === "lifecycle_sim" ? <label className="flex flex-col gap-0.5"><span className="text-muted-foreground">scenario source</span>
          <select aria-label="scenario source" value={f.scenario_source} onChange={(e) => setF({ ...f, scenario_source: e.target.value })} className="h-8 rounded border border-input bg-transparent px-1">
            <option value="simulated_from_start">simulated from the start date (no hindsight)</option>
            <option value="history_then_simulated">actual history from the start date, then simulated</option></select></label> : null}
        {num("n_paths", 100, "paths")}
        {kind === "historical_replay" ? <label className="flex items-center gap-1"><input type="checkbox" checked={f.experiments} onChange={(e) => setF({ ...f, experiments: e.target.checked })} />
          validation experiments (+3 min)</label> : null}
      </div>
      {kind === "lifecycle_sim" ? <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="policies">
        {Object.keys(POLICY_LABELS).map((p) => <label key={p} className="flex items-center gap-1 rounded border border-border px-2 py-0.5">
          <input type="checkbox" checked={f.policies.includes(p)} onChange={(e) => setF({ ...f, policies: e.target.checked ? [...f.policies, p] : f.policies.filter((x) => x !== p) })} />{POLICY_LABELS[p]}</label>)}
      </div> : null}
      <button onClick={submit} className="mt-3 rounded-full border border-border bg-background px-4 py-1.5 text-sm hover:bg-muted" data-testid={kind + "-run"}>
        Run with these assumptions</button>
      <span className="ml-3 text-muted-foreground">The page follows your run and shows its progress, then its results. Identical assumptions reuse the cached run.</span>
    </div>
  );
}

function Body({ env }: { env: any }) {
  const r = env.results;
  const runId = env.run_id as string;
  const t = useVizTokens();
  const color = useAssetColor();
  const pols = Object.keys(r.policies).filter((p) => r.policies[p].available && r.policies[p].forward?.available);
  const [pol, setPol] = useState(pols[0]);
  const P = r.policies[pol];
  const f = P?.forward;
  const sleeves: string[] = f?.forward_universe ?? r.eligible;
  const growth = sleeves.filter((c) => r.block_of[c] === "growth");
  const hist = P?.history;
  const retAge = r.investor.retirement_age;
  if (!P || !f) return <Warnings items={["No policy produced a forward simulation: " + Object.entries(r.policies).map(([k, v]: any) => k + " — " + (v.reason ?? v.forward?.reason)).join("; ")]} />;
  const ages = f.allocation_by_age.map((a: any) => a.age);
  return (
    <div className="space-y-4">
      <ContextBar items={[["Start", r.start + " at age " + r.investor.start_age], ["Scenario", r.scenario_source.replace(/_/g, " ")], ["Information until", r.information_until],
        ["Paths", f.paths], ["Universe", sleeves.join(", ")], ["Run", runId.slice(0, 10)]]} />
      <Warnings items={[...(r.warnings ?? []), ...((f.excluded_short_history ?? r.excluded_short_history ?? []).length
        ? ["Excluded from the forward universe (less than 15 years of history at the information date, not proxied): " + (f.excluded_short_history ?? r.excluded_short_history).join(", ")] : []),
        ...Object.entries(r.policies).filter(([, v]: any) => !v.available).map(([k, v]: any) => k + ": " + v.reason)]} />
      <label className="flex items-center gap-2 text-xs">Policy
        <select aria-label="simulation policy" value={pol} onChange={(e) => setPol(e.target.value)} className="h-7 rounded border border-input bg-transparent px-1">
          {pols.map((p) => <option key={p} value={p}>{r.labels[p] ?? p}</option>)}</select></label>
      <Grid>
        <Viz id="LS-01" runId={runId} cls="model_generated" selection={{ policy: pol }}>
          <Plot height={320} data={[...sleeves.map((c, k) => ({ x: [...(hist ? hist.ages : []), ...ages],
            y: [...(hist ? hist.w_post.map((w: number[]) => w[r.candidates.indexOf(c)]) : []), ...f.allocation_by_age.map((a: any) => a.mean[c] ?? 0)],
            type: "scatter", mode: "lines", stackgroup: "w", name: c, line: { width: 0.5, color: color(c, k) } }))] as Data[]}
            layout={{ yaxis: { tickformat: ".0%", range: [0, 1] }, xaxis: { title: { text: "age" } },
              shapes: [{ type: "line", x0: retAge, x1: retAge, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: t.text2 } },
                ...(hist ? [{ type: "line", x0: f.start_age, x1: f.start_age, yref: "paper", y0: 0, y1: 1, line: { dash: "dot", color: t.text } }] : [])] as any }} />
          {hist ? <div className="text-[11px] text-muted-foreground">Left of the dotted line: realised history (one investor); right: mean across simulated paths.</div> : null}
        </Viz>
        <Viz id="LS-02" runId={runId} cls="model_generated" selection={{ policy: pol }}>
          {(() => {
            const g = f.allocation_by_age.map((a: any) => growth.reduce((s: number, c: string) => s + (a.mean[c] ?? 0), 0));
            const lo = f.allocation_by_age.map((a: any) => growth.reduce((s: number, c: string) => s + (a.q[c]?.[0] ?? 0), 0));
            const hi = f.allocation_by_age.map((a: any) => growth.reduce((s: number, c: string) => s + (a.q[c]?.[2] ?? 0), 0));
            return <Plot height={320} data={[{ x: [...ages, ...ages.slice().reverse()], y: [...hi, ...lo.slice().reverse()], fill: "toself", type: "scatter", mode: "lines",
              line: { width: 0 }, fillcolor: "rgba(57,135,229,0.2)", name: "10–90% (sum of sleeve percentiles)" },
              { x: ages, y: g, type: "scatter", mode: "lines", name: "mean growth share", line: { color: t.series[0], width: 2 } }] as Data[]}
              layout={{ yaxis: { tickformat: ".0%", range: [0, 1] }, xaxis: { title: { text: "age" } } }} />;
          })()}
        </Viz>
        <Viz id="LS-03" runId={runId} cls="model_generated" selection={{ policy: pol }}>
          <Plot height={320} data={[
            ...[[0, 4, "5–95%"], [1, 3, "25–75%"]].map(([lo, hi, nm]: any, k) => ({ x: [...f.wealth_by_age.map((q: any) => q.age), ...f.wealth_by_age.map((q: any) => q.age).reverse()],
              y: [...f.wealth_by_age.map((q: any) => q.q[hi]), ...f.wealth_by_age.map((q: any) => q.q[lo]).reverse()], fill: "toself", type: "scatter", mode: "lines", name: nm,
              line: { width: 0 }, fillcolor: k ? "rgba(57,135,229,0.30)" : "rgba(57,135,229,0.15)" })),
            { x: f.wealth_by_age.map((q: any) => q.age), y: f.wealth_by_age.map((q: any) => q.q[2]), name: "median", type: "scatter", mode: "lines", line: { color: t.series[0], width: 2 } },
            ...(hist ? [{ x: hist.ages, y: hist.wealth_real, name: "realised history", type: "scatter", mode: "lines", line: { color: t.text, width: 2 } }] : []),
            ...pols.filter((p) => p !== pol).slice(0, 3).map((p, k) => ({ x: r.policies[p].forward.wealth_by_age.map((q: any) => q.age), y: r.policies[p].forward.wealth_by_age.map((q: any) => q.q[2]),
              name: p + " median", type: "scatter", mode: "lines", line: { dash: "dot", width: 1, color: t.series[k + 1] } }))] as Data[]}
            layout={{ yaxis: { tickformat: "$~s" }, xaxis: { title: { text: "age" } },
              shapes: [{ type: "line", x0: retAge, x1: retAge, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: t.text2 } }] as any }} />
        </Viz>
        <Viz id="LS-04" runId={runId} cls="model_generated">
          <DataTable rows={pols.map((p) => ({ policy: r.labels[p] ?? p, ...r.policies[p].forward, w_ret: r.policies[p].forward.wealth_at_retirement?.[2],
            w_ret_lo: r.policies[p].forward.wealth_at_retirement?.[0], hist_w: r.policies[p].history?.final_wealth }))} columns={[
            { key: "policy", label: "policy" }, { key: "ce_consumption", label: "lifetime CE $/yr", fmt: usd }, { key: "p_no_shortfall", label: "P(no shortfall)", fmt: (v) => pct(v) },
            { key: "unmet_cvar95", label: "unmet CVaR95", fmt: usd }, { key: "w_ret", label: "median wealth at retirement", fmt: usd }, { key: "w_ret_lo", label: "5% wealth at retirement", fmt: usd },
            ...(hist ? [{ key: "hist_w", label: "realised wealth today", fmt: usd }] : [])]} />
        </Viz>
        <Viz id="LS-05" runId={runId} cls="observed">
          <DataTable rows={pols.map((p) => ({ policy: r.labels[p] ?? p, ...(r.policies[p].initial_target ?? (r.policies[p].forward?.start_holdings
            ? Object.fromEntries(Object.entries(r.policies[p].forward.start_holdings).map(([k, v]: any) => [k, v / Math.max(r.policies[p].forward.start_wealth, 1)])) : {})) }))}
            columns={[{ key: "policy", label: "policy" }, ...sleeves.map((c) => ({ key: c, label: c, fmt: (v: any) => pct(v) }))]} />
          <div className="mt-1 text-[11px] text-muted-foreground">Information until {r.information_until}; forward universe {sleeves.join(", ")}.</div>
        </Viz>
      </Grid>
    </div>
  );
}

/** Interactive Lifecycle Simulator › Multi-asset engine (dated start, all asset classes, state-dependent policies). */
export function MultiAssetSimulator() {
  return (
    <StudyGate kind="lifecycle_sim" title="Multi-asset lifecycle simulation" runLabel="Run the 2007 preset"
      description="A 20-year-old starting in January 2007 with $10,000 and a $45,000 salary, simulated to 95 with four multi-asset policies (about 10 seconds)."
      controls={(run, shown) => <InvestorStartForm shown={shown} onRun={run} kind="lifecycle_sim" />}>
      {(env) => <Body env={env} />}
    </StudyGate>
  );
}
