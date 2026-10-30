"use client";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Data } from "plotly.js";
import { toast } from "sonner";
import { DeltaHeatmap } from "@/components/charts/Heatmap";
import { Plot, useVizTokens } from "@/components/charts/Plot";
import { PageHeader, Section } from "@/components/common/Section";
import { Field, NativeSelect } from "@/components/common/Fields";
import { Stat } from "@/components/common/Stat";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { ExpandableCard } from "@/components/ui/expandable-card";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";
import { ResultSummary } from "@/components/experiment/ResultSummary";
import { InlineProgress } from "@/components/experiment/RunProgress";
import { Provenance } from "@/components/experiment/Provenance";
import { apiGet, apiPost } from "@/lib/api/client";
import { useResults, useSurface, useSweeps } from "@/lib/api/hooks";
import type { RunRow, SweepCell } from "@/lib/api/types";
import { BENCHMARK_LABELS, assetLabel, pct, signedPct } from "@/lib/format";
import { useQuery } from "@tanstack/react-query";

/* eslint-disable @typescript-eslint/no-explicit-any */
interface Selector {
  kind: "decumulation" | "accumulation";
  universe: "core" | "modern";
  generator: string;
  gamma: string;
  optimizer: string;
}

function sweepMatches(row: RunRow, sel: Selector, spec: any): boolean {
  if (!spec) return false;
  return (
    spec.kind === sel.kind &&
    spec.base?.data?.universe === sel.universe &&
    spec.base?.scenario?.generator === sel.generator &&
    String(spec.base?.preferences?.gamma ?? 4) === String(Number(sel.gamma)) &&
    spec.optimizer === sel.optimizer
  );
}

function CellDetail({ cell, surfaceKind, benchmark, xLabel, yLabel, onClose }: {
  cell: SweepCell; surfaceKind: string; benchmark: string; xLabel: string; yLabel: string; onClose: () => void;
}) {
  const res = useResults(cell.run_id);
  const router = useRouter();
  const b = cell.benchmarks[benchmark];
  async function compareAgainstBenchmark() {
    if (!res.data) return;
    const spec = JSON.parse(JSON.stringify(res.data.spec));
    spec.policy = { ...spec.policy, type: benchmark, params: {} };
    spec.data = { ...spec.data, catalog_hash: null };
    try {
      const bench = await apiPost<{ status: string }>("/v1/experiments", spec);
      const cmp = await apiPost<{ status: string }>("/v1/compare", { run_ids: [bench.run_id, cell.run_id] });
      router.push("/compare?id=" + cmp.run_id);
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }
  const r = res.data?.results;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-wider text-muted-foreground">{surfaceKind} cell</div>
          <h2 className="text-lg font-semibold">
            {xLabel} {surfaceKind === "decumulation" ? pct(cell.x, 1) : pct(cell.x, 0)} · {yLabel} {cell.y}
          </h2>
          <div className="mt-1 text-sm text-muted-foreground">
            {cell.policy} — ΔCE vs {BENCHMARK_LABELS[benchmark]} <b className="text-foreground">{signedPct(b?.delta)}</b> ± {pct(b?.se, 2)}
            {b && !b.significant ? <Badge variant="outline" className="ml-2">within 2 SE</Badge> : null}
          </div>
        </div>
        <HoverBorderGradient onClick={compareAgainstBenchmark} containerClassName="rounded-full" className="bg-background px-4 py-1.5 text-sm text-foreground">
          Compare against benchmark
        </HoverBorderGradient>
      </div>
      {cell.weights ? (
        <div className="flex flex-wrap gap-2 text-xs">
          {Object.entries(cell.weights).filter(([, v]) => v > 0.005).map(([k, v]) => (
            <Badge key={k} variant="secondary">{assetLabel(k)} {pct(v, 0)}</Badge>
          ))}
          {cell.theta ? <Badge variant="outline">θ = [{cell.theta.map((v) => v.toFixed(2)).join(", ")}]</Badge> : null}
        </div>
      ) : null}
      {r ? (
        <ResultSummary r={r} runId={cell.run_id} retireAge={res.data?.spec?.investor?.retirement_age} compact />
      ) : (
        <div className="h-64 animate-pulse rounded-lg bg-muted/40" />
      )}
      {res.data?.spec ? (
        <details className="rounded-lg border border-border p-3 text-xs">
          <summary className="cursor-pointer text-muted-foreground">Assumptions (exact ExperimentSpec)</summary>
          <pre className="mt-2 overflow-x-auto">{JSON.stringify(res.data.spec, null, 2)}</pre>
        </details>
      ) : null}
      <button className="text-xs text-muted-foreground underline" onClick={onClose}>close</button>
    </div>
  );
}

export function WithdrawalLab() {
  const params = useSearchParams();
  const [sel, setSel] = useState<Selector>({
    kind: (params.get("kind") as Selector["kind"]) ?? "decumulation",
    universe: (params.get("universe") as Selector["universe"]) ?? "core",
    generator: params.get("generator") ?? "bootstrap",
    gamma: params.get("gamma") ?? "4",
    optimizer: params.get("optimizer") ?? "parametric",
  });
  const [benchmark, setBenchmark] = useState(sel.kind === "accumulation" ? "target_date" : "sixty_forty");
  const [showSE, setShowSE] = useState(true);
  const [active, setActive] = useState<[number, number] | null>(null);
  const sweeps = useSweeps();
  const t = useVizTokens();

  const specs = useMemo(() => {
    const out: Record<string, any> = {};
    for (const s of sweeps.data?.sweeps ?? []) out[s.run_id] = (s as RunRow & { spec?: any }).spec;
    return { data: out };
  }, [sweeps.data]);
  const match = useMemo(() => {
    for (const s of sweeps.data?.sweeps ?? []) {
      if (sweepMatches(s, sel, specs.data?.[s.run_id])) return s;
    }
    return null;
  }, [sweeps.data, specs.data, sel]);
  const siblings = useMemo(() => {
    const out: string[] = [];
    for (const s of sweeps.data?.sweeps ?? []) {
      const sp = specs.data?.[s.run_id];
      if (!sp || s.status !== "done") continue;
      if (sp.kind === sel.kind && sp.base?.data?.universe === sel.universe && String(sp.base?.preferences?.gamma ?? 4) === String(Number(sel.gamma)) && sp.optimizer === sel.optimizer) out.push(s.run_id);
    }
    return out;
  }, [sweeps.data, specs.data, sel]);
  const surface = useSurface(match?.run_id ?? null);
  const surf = surface.data?.surface;
  const benchKey = surf && surf.benchmarks.includes(benchmark) ? benchmark : surf?.benchmarks[0] ?? benchmark;
  const disagreement = useQuery({
    queryKey: ["disagree", siblings.join(","), benchKey],
    enabled: siblings.length >= 2,
    queryFn: () => apiGet<any>("/v1/sweeps/disagreement", { ids: siblings.join(","), benchmark: benchKey }),
  });

  async function launch() {
    const body = {
      kind: sel.kind,
      optimizer: sel.optimizer,
      base: { data: { universe: sel.universe }, scenario: { generator: sel.generator, n_paths: 2000, n_train_paths: 1000 },
        preferences: { gamma: Number(sel.gamma) } },
      benchmarks: sel.kind === "accumulation" ? ["target_date", "sixty_forty", "best_constant"] : ["sixty_forty", "target_date", "best_constant"],
      label: `${sel.kind} ${sel.universe} ${sel.generator} γ=${sel.gamma} ${sel.optimizer}`,
    };
    try {
      await apiPost("/v1/sweeps", body);
      toast.success("Sweep submitted — cells stream into the registry as they finish");
      sweeps.refetch();
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }

  const xFormat = (v: number) => (sel.kind === "decumulation" ? (v * 100).toFixed(1) + "%" : (v * 100).toFixed(0) + "%");
  const cell = surf && active ? surf.cells[active[0]][active[1]] : null;
  const m = surf ? surf.matrices[benchKey] : null;
  const opt = <T extends string>(v: T, l: string) => ({ value: v, label: l });

  return (
    <div>
      <PageHeader eyebrow="04" title="Withdrawal-Rate Sensitivity Lab"
        description="Each cell is the percentage gain in certainty-equivalent consumption of the optimised policy over the benchmark, on common random numbers. Hatched cells are within 2 Monte Carlo SEs of zero. Click a cell for the policy behind it." />
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Surface"><NativeSelect value={sel.kind} onChange={(v) => { setSel({ ...sel, kind: v }); setBenchmark(v === "accumulation" ? "target_date" : "sixty_forty"); setActive(null); }}
          options={[opt("decumulation", "Decumulation: withdrawal × years to retirement"), opt("accumulation", "Accumulation: savings × age")]} /></Field>
        <Field label="Benchmark"><NativeSelect value={benchmark} onChange={setBenchmark}
          options={[opt("sixty_forty", "60/40"), opt("target_date", "Target-date"), opt("best_constant", "Best constant mix")]} /></Field>
        <Field label="γ"><NativeSelect value={sel.gamma} onChange={(v) => setSel({ ...sel, gamma: v })} options={[opt("2", "2"), opt("4", "4"), opt("6", "6")]} /></Field>
        <Field label="Scenario model"><NativeSelect value={sel.generator} onChange={(v) => setSel({ ...sel, generator: v })}
          options={[opt("bootstrap", "Block bootstrap"), opt("student_t", "Student-t"), opt("markov_switching", "Markov switching"), opt("curve_factor", "Yield-curve factors")]} /></Field>
        <Field label="Universe"><NativeSelect value={sel.universe} onChange={(v) => setSel({ ...sel, universe: v })}
          options={[opt("core", "Long-history core"), opt("modern", "Modern diversified")]} /></Field>
        <Field label="Optimised policy"><NativeSelect value={sel.optimizer} onChange={(v) => setSel({ ...sel, optimizer: v })}
          options={[opt("parametric", "Parametric dynamic"), opt("glidepath", "Fitted glidepath"), opt("best_constant", "Best constant"), opt("utility_static", "Static CRRA")]} /></Field>
        <label className="flex items-center gap-2 pb-1 text-xs text-muted-foreground"><Switch checked={showSE} onCheckedChange={setShowSE} /> SE hatching</label>
      </div>

      {!match ? (
        <Section>
          <div className="flex flex-col items-center gap-3 py-12 text-center text-sm text-muted-foreground">
            <span>No cached sweep for this combination yet.</span>
            <HoverBorderGradient onClick={launch} containerClassName="rounded-full" className="bg-background px-5 py-2 text-sm text-foreground">
              Run this sweep
            </HoverBorderGradient>
            <span className="text-xs">2,000 paths per cell; a full surface takes several minutes on a laptop.</span>
          </div>
        </Section>
      ) : surface.data && surface.data.status !== "done" ? (
        <Section title="Sweep running" description={match.label ?? match.run_id}>
          <InlineProgress stage={surface.data.stage} progress={surface.data.progress} />
        </Section>
      ) : surf && m ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Mean ΔCE" value={signedPct(m.delta.flat().reduce((a, b) => a + b, 0) / m.delta.flat().length)} sub={"vs " + BENCHMARK_LABELS[benchKey]} />
            <Stat label="Best cell" value={signedPct(Math.max(...m.delta.flat()))} />
            <Stat label="Cells beyond 2 SE" value={pct(m.delta.flat().filter((v, i) => Math.abs(v) > 2 * m.se.flat()[i]).length / m.delta.flat().length, 0)} />
            <Stat label="Cells" value={surf.cells.length * surf.cells[0].length} sub={surf.summary.optimizer + " · " + surf.summary.generator} />
          </div>
          <Section title={`ΔCE vs ${BENCHMARK_LABELS[benchKey]} (%)`} description={`${surf.y_label} (rows) × ${surf.x_label} (columns). Diverging scale centred at zero.`}>
            <DeltaHeatmap x={surf.x} y={surf.y} z={m.delta} se={m.se} shortfall={surf.shortfall} xLabel={surf.x_label} yLabel={surf.y_label}
              xFormat={xFormat} showSE={showSE} onCellClick={(i, j) => setActive([i, j])} selected={active} />
            <Provenance meta={{ run_id: match.run_id, spec_hash: match.spec_hash, catalog_hash: match.catalog_hash ?? "", engine_version: match.engine_version }} runId={match.run_id} />
          </Section>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Depletion probability (optimised policy)" description="Share of paths with unfunded planned spending at some point.">
              <Plot height={300} data={[{ type: "heatmap", x: surf.x.map(xFormat), y: surf.y.map(String), z: surf.shortfall, zmin: 0,
                colorscale: [[0, t.divMid], [1, t.series[0]]], xgap: 2, ygap: 2, texttemplate: "%{z:.0%}",
                hovertemplate: "%{x} · %{y}: %{z:.1%}<extra></extra>", colorbar: { thickness: 10, tickformat: ".0%" } } as Data]}
                layout={{ hovermode: "closest", xaxis: { type: "category", title: { text: surf.x_label } }, yaxis: { type: "category", title: { text: surf.y_label } } }} />
            </Section>
            <Section title="Model-disagreement map" description="Cells where scenario generators disagree on the sign of a significant ΔCE are flagged.">
              {siblings.length < 2 ? (
                <div className="py-10 text-center text-xs text-muted-foreground">Needs this surface for at least two generators (same γ, universe and optimiser).</div>
              ) : disagreement.data ? (
                <Plot height={300} data={[{ type: "heatmap", x: disagreement.data.x.map(xFormat), y: disagreement.data.y.map(String),
                  z: disagreement.data.disagree.map((r: boolean[]) => r.map((v) => (v ? 1 : 0))), zmin: 0, zmax: 1,
                  colorscale: [[0, t.divMid], [1, t.series[1]]], showscale: false, xgap: 2, ygap: 2,
                  customdata: disagreement.data.n_positive.map((r: number[], i: number) => r.map((v, j) => [v, disagreement.data.n_negative[i][j]])),
                  hovertemplate: "%{x} · %{y}<br>generators positive: %{customdata[0]}, negative: %{customdata[1]}<extra></extra>" } as Data]}
                  layout={{ hovermode: "closest", xaxis: { type: "category" }, yaxis: { type: "category" } }} />
              ) : <div className="h-60 animate-pulse rounded bg-muted/40" />}
              {disagreement.data ? <div className="mt-1 text-[11px] text-muted-foreground">Generators: {disagreement.data.generators.join(", ")}</div> : null}
            </Section>
          </div>
        </div>
      ) : (
        <div className="h-96 animate-pulse rounded-xl bg-muted/40" />
      )}

      <ExpandableCard open={!!cell} layoutId="heatmap-cell" onClose={() => setActive(null)}>
        {cell && surf ? (
          <CellDetail cell={cell} surfaceKind={surf.kind} benchmark={benchKey} xLabel={surf.x_label} yLabel={surf.y_label} onClose={() => setActive(null)} />
        ) : null}
      </ExpandableCard>
    </div>
  );
}
