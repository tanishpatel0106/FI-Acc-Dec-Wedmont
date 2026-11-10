"use client";
import Link from "next/link";
import { Viz } from "@/components/visualizations/VisualizationFrame";
import { useCatalog, useOverview } from "@/lib/api/hooks";
import { BENCHMARK_LABELS, pct, signedPct } from "@/lib/format";

function Kpi({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="flex h-full min-h-24 flex-col justify-center rounded-lg bg-muted/40 px-4">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {sub ? <div className="text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

/** Headline results of the CE utility sweeps and the registry counts (from the original overview). */
export function SweepHeadlines() {
  const ov = useOverview();
  const cat = useCatalog();
  const dec = ov.data?.latest_sweeps?.decumulation;
  const acc = ov.data?.latest_sweeps?.accumulation;
  const c = ov.data?.counts ?? {};
  return (
    <Viz id="OV-09" cls="model_generated" empty={ov.isError ? "API unreachable: start it with make api." : null}
      footnote={<Link className="underline" href="/withdrawal-lab?section=utility">Open the CE utility sweeps →</Link>}>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Best-cell ΔCE (decumulation)" value={dec ? signedPct(dec.max_delta) : "Not computed"}
          sub={dec ? `vs ${BENCHMARK_LABELS[dec.benchmark] ?? dec.benchmark}, ${dec.universe}, γ=${dec.gamma}` : "no completed sweep (make seed)"} />
        <Kpi label="Mean ΔCE across cells" value={dec ? signedPct(dec.mean_delta) : "Not computed"}
          sub={dec ? `${pct(dec.share_significant, 0)} of cells beyond 2 SE` : undefined} />
        <Kpi label="Accumulation mean ΔCE" value={acc ? signedPct(acc.mean_delta) : "Not computed"}
          sub={acc ? `vs ${BENCHMARK_LABELS[acc.benchmark] ?? acc.benchmark}` : undefined} />
        <Kpi label="Data as of (last observation)" value={cat.data?.as_of ?? "–"}
          sub={cat.data ? (cat.data.wrds ? "WRDS + public sources" : "Public sources only · WRDS not ingested") : "connecting…"} />
      </div>
      <div className="mt-2 text-[11px] text-muted-foreground">Registry: {c.experiment ?? 0} experiments · {c.sweep ?? 0} sweeps · {c.compare ?? 0} comparisons · {c.validation ?? 0} validations</div>
    </Viz>
  );
}
