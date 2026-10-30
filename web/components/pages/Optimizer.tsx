"use client";
import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import type { Data } from "plotly.js";
import { toast } from "sonner";
import { Plot, useVizTokens } from "@/components/charts/Plot";
import { WeightPath } from "@/components/charts/WeightPath";
import { PageHeader, Section } from "@/components/common/Section";
import { Field, NativeSelect } from "@/components/common/Fields";
import { Stat } from "@/components/common/Stat";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";
import { ExpandableCard } from "@/components/ui/expandable-card";
import { Badge } from "@/components/ui/badge";
import { ResultSummary } from "@/components/experiment/ResultSummary";
import { InlineProgress } from "@/components/experiment/RunProgress";
import { apiGet, apiPost } from "@/lib/api/client";
import { useResults, useRunStatus } from "@/lib/api/hooks";
import type { ExperimentResults, RunStatus } from "@/lib/api/types";
import { specFromBuilder, useBuilder } from "@/lib/store";
import { num, pct, signedPct, usd } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
const FAMILY = [
  { type: "sixty_forty", label: "60/40" },
  { type: "target_date", label: "Target-date" },
  { type: "best_constant", label: "Best constant" },
  { type: "glidepath", label: "Fitted glidepath" },
  { type: "risk_parity", label: "Risk parity" },
  { type: "mean_cvar", label: "Mean–CVaR" },
  { type: "utility_static", label: "Static CRRA" },
  { type: "regime", label: "Regime-dependent" },
  { type: "bucket", label: "Liability bucket" },
  { type: "parametric", label: "Parametric dynamic" },
];

function DPPanel() {
  const s = useBuilder();
  const [runId, setRunId] = useState<string | null>(null);
  const [regime, setRegime] = useState("0");
  const status = useRunStatus(runId);
  const res = useResults(runId, status.data?.status === "done");
  const t = useVizTokens();
  async function run() {
    const { set: _s, ...state } = s;
    void _s;
    const spec = specFromBuilder({ ...state, generator: "markov_switching" }, "dp");
    try {
      const r = await apiPost<{ status: string }>("/v1/experiments", spec);
      setRunId(r.run_id);
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }
  const r = res.data?.results;
  const surf = r?.surfaces;
  const reg = Number(regime);
  return (
    <Section title="Grid dynamic programming (ground truth on the reduced problem)"
      description="US equity / 10Y Treasury / T-bills × Markov-switching regimes; 200-point cash-on-hand grid, 21-point simplex, golden-section consumption, annual decisions."
      actions={<HoverBorderGradient onClick={run} containerClassName="rounded-full" className="bg-background px-4 py-1.5 text-sm text-foreground">Solve DP</HoverBorderGradient>}>
      {status.data && status.data.status !== "done" ? <InlineProgress stage={status.data.stage} progress={status.data.progress} /> : null}
      {status.data?.status === "failed" ? <pre className="text-xs text-destructive">{status.data.error}</pre> : null}
      {r && surf ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="DP CE (annual model)" value={usd(r.ce.policy.ce)} sub={"± " + usd(r.ce.policy.se)} />
            <Stat label="60/40 + fixed real" value={usd(r.ce.benchmark?.ce)} />
            <Stat label="ΔCE (in-model)" value={signedPct(r.ce.delta?.delta)} sub={"± " + pct(r.ce.delta?.se, 2)} />
            <Stat label="H1 slope ∂w/∂q (first age)" value={num(r.h1?.[0]?.slope, 3)} sub="equity weight per unit net-flow rate" />
          </div>
          <div className="flex items-center gap-3">
            <Field label="Regime"><NativeSelect value={regime} onChange={setRegime} options={surf.by_regime.map((_, i) => ({ value: String(i), label: "Regime " + i }))} /></Field>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Optimal equity weight (age × cash-on-hand)">
              <Plot height={320} data={[{ type: "heatmap", x: surf.x, y: surf.by_regime[reg].map((row) => row.age),
                z: surf.by_regime[reg].map((row) => row.equity), zmin: 0, zmax: 1, colorscale: [[0, t.divMid], [1, t.series[0]]],
                hovertemplate: "age %{y}, x %{x:.1f}: %{z:.0%}<extra></extra>", colorbar: { thickness: 10, tickformat: ".0%" } } as Data]}
                layout={{ hovermode: "closest", xaxis: { type: "log", title: { text: "cash-on-hand / permanent income" } }, yaxis: { title: { text: "Age" } } }} />
            </Section>
            <Section title="Lifecycle transition: equity weight against q" description="Headline exhibit 3 — optimal allocation vs signed net-flow rate at fixed ages.">
              <Plot height={320} data={surf.by_regime[reg].map((row, i) => ({ x: row.q, y: row.equity, type: "scatter", mode: "lines",
                name: "age " + row.age, line: { width: 2, color: t.series[i % 8] } })) as Data[]}
                layout={{ xaxis: { title: { text: "q = (c − y) / x" }, range: [-1, 1] }, yaxis: { tickformat: ".0%", range: [0, 1.02] } }} />
            </Section>
          </div>
          <WeightPath ages={r.ages} assets={r.weights_path.assets} weights={r.weights_path.mean} height={260} />
          <div className="flex flex-wrap gap-2">{(r.warnings ?? []).map((w) => <Badge key={w} variant="outline">⚠ {w}</Badge>)}</div>
        </div>
      ) : !runId ? <div className="py-8 text-center text-sm text-muted-foreground">Uses the investor from the Simulator builder.</div> : null}
    </Section>
  );
}

export function Optimizer() {
  const s = useBuilder();
  const [ids, setIds] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<string | null>(null);
  const t = useVizTokens();
  const statuses = useQueries({
    queries: FAMILY.map((f) => ({
      queryKey: ["status", ids[f.type]],
      enabled: !!ids[f.type],
      queryFn: () => apiGet<RunStatus>("/v1/experiments/" + ids[f.type]),
      refetchInterval: (q: any) => (q.state.data?.status === "done" || q.state.data?.status === "failed" ? false : 2000),
    })),
  });
  const results = useQueries({
    queries: FAMILY.map((f, i) => ({
      queryKey: ["results", ids[f.type]],
      enabled: !!ids[f.type] && statuses[i].data?.status === "done",
      queryFn: () => apiGet<{ results: ExperimentResults }>("/v1/experiments/" + ids[f.type] + "/results"),
      staleTime: Infinity,
    })),
  });
  async function runAll() {
    const { set: _s, ...state } = s;
    void _s;
    const next: Record<string, string> = {};
    for (const f of FAMILY) {
      const spec = specFromBuilder({ ...state, benchmark: "sixty_forty" }, f.type);
      try {
        const r = await apiPost<{ status: string }>("/v1/experiments", spec);
        next[f.type] = r.run_id as string;
      } catch (e) {
        toast.error(f.label + ": " + String((e as Error).message));
      }
    }
    setIds(next);
  }
  const done = FAMILY.map((f, i) => ({ f, r: results[i].data?.results, st: statuses[i].data }));
  const ready = done.filter((d) => d.r);
  const openItem = done.find((d) => d.f.type === open);
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="03" title="Utility & Policy Optimizer"
        description="Static, regime-dependent and dynamic policies fitted on seed-set A and reported on seed-set B, all on the same scenario paths as the 60/40 benchmark. Investor and preferences come from the Simulator builder.">
        <HoverBorderGradient onClick={runAll} containerClassName="rounded-full" className="bg-background px-5 py-2 text-sm text-foreground">
          Optimise policy family
        </HoverBorderGradient>
      </PageHeader>
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        <Badge variant="outline">{s.universe}</Badge><Badge variant="outline">{s.generator}</Badge>
        <Badge variant="outline">age {s.startAge} → retire {s.retirementAge}</Badge><Badge variant="outline">γ = {s.gamma}</Badge>
        <Badge variant="outline">{s.spendingRule} {pct(s.withdrawalRate, 1)}</Badge><Badge variant="outline">{s.nPaths} paths</Badge>
      </div>
      <Section title="ΔCE vs 60/40 with paired Monte Carlo SE" description="Whiskers are ±2 SE from paired path utilities. Click a policy for its weights, fans and shortfall.">
        {Object.keys(ids).length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Press “Optimise policy family”.</div>
        ) : (
          <>
            <Plot height={340} onClick={(e) => { const p = e.points?.[0]; if (p) setOpen(FAMILY.find((f) => f.label === p.x)?.type ?? null); }}
              data={[{ type: "bar", x: ready.map((d) => d.f.label), y: ready.map((d) => (d.r!.ce.delta?.delta ?? 0) * 100),
                error_y: { type: "data", array: ready.map((d) => 2 * (d.r!.ce.delta?.se ?? 0) * 100), color: t.text2, thickness: 1.5, width: 4 },
                marker: { color: ready.map((d) => ((d.r!.ce.delta?.delta ?? 0) >= 0 ? t.series[0] : t.series[7])) },
                customdata: ready.map((d) => [d.r!.ce.policy.ce, d.r!.shortfall?.p_depletion ?? 0]) as any,
                hovertemplate: "%{x}<br>ΔCE %{y:+.2f}%<br>CE $%{customdata[0]:,.0f}<br>P(depletion) %{customdata[1]:.1%}<extra></extra>" } as Data]}
              layout={{ hovermode: "closest", yaxis: { title: { text: "ΔCE %" }, zeroline: true }, showlegend: false }} />
            <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-5">
              {done.map((d) => (
                <button key={d.f.type} onClick={() => d.r && setOpen(d.f.type)}
                  className="rounded-lg border border-border p-2 text-left text-xs hover:bg-muted/50">
                  <div className="font-medium">{d.f.label}</div>
                  {d.r ? <div className="tabular-nums text-muted-foreground">{usd(d.r.ce.policy.ce)} · {signedPct(d.r.ce.delta?.delta)}</div>
                    : d.st ? <div className="text-muted-foreground">{d.st.status === "failed" ? "failed" : d.st.stage.replace(/_/g, " ")}</div> : <div className="text-muted-foreground">–</div>}
                </button>
              ))}
            </div>
          </>
        )}
      </Section>
      {ready.length > 0 ? (
        <Section title="Optimal growth-asset share by age" description="Mean across paths at the start of each year.">
          <Plot height={300} data={ready.map((d, i) => ({ x: d.r!.ages, y: d.r!.risky_share?.mean ?? [], type: "scatter", mode: "lines",
            name: d.f.label, line: { width: 2, color: t.series[i % 8] } })) as Data[]}
            layout={{ yaxis: { tickformat: ".0%", range: [0, 1.02] }, xaxis: { title: { text: "Age" } } }} />
        </Section>
      ) : null}
      <DPPanel />
      <ExpandableCard open={!!openItem?.r} layoutId="policy-card" onClose={() => setOpen(null)}>
        {openItem?.r ? (
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">{openItem.f.label}</h2>
            <pre className="overflow-x-auto rounded-lg bg-muted/40 p-2 text-[11px]">{JSON.stringify(openItem.r.policy, null, 2)}</pre>
            <ResultSummary r={openItem.r} runId={ids[openItem.f.type]} retireAge={s.retirementAge} compact />
          </div>
        ) : null}
      </ExpandableCard>
    </div>
  );
}
