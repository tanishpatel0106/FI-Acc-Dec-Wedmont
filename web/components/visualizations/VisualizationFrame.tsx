"use client";
import { useEffect, useRef, useState } from "react";
import { IconAlertTriangle, IconChartBar, IconDownload, IconLink, IconTable } from "@tabler/icons-react";
import { exportUrl } from "@/lib/api/v2";
import { shortId } from "@/lib/format";
import { cn } from "@/lib/utils";
import { vizEntry } from "@/lib/research/visualization-registry";
import { VisualizationInfo } from "./VisualizationInfo";
import { useProvenance, type Provenance } from "./provenance";

/* eslint-disable @typescript-eslint/no-explicit-any */
export type DataClass = "observed" | "model_generated" | "illustrative" | "unavailable";

const CLASS_STYLE: Record<DataClass, string> = {
  observed: "border-[var(--viz-s3)]/50 text-[var(--viz-s3)]",
  model_generated: "border-[var(--viz-s4)]/50 text-[var(--viz-s4)]",
  illustrative: "border-[var(--viz-s5)]/50 text-[var(--viz-s5)]",
  unavailable: "border-border text-muted-foreground",
};
const CLASS_LABEL: Record<DataClass, string> = {
  observed: "Observed", model_generated: "Model-generated", illustrative: "Illustrative", unavailable: "Unavailable",
};

export function DataTag({ cls }: { cls: DataClass }) {
  return <span className={cn("rounded border px-1.5 py-px text-[10px] font-medium uppercase tracking-wide", CLASS_STYLE[cls])}>{CLASS_LABEL[cls]}</span>;
}

export function GradeTag({ grade }: { grade?: string | null }) {
  const g = (grade ?? "not_computed") as string;
  const tone = g === "robust" || g === "supported" ? "text-[var(--viz-s3)] border-[var(--viz-s3)]/50"
    : g === "contradicted" || g === "invalid" ? "text-[var(--viz-s8)] border-[var(--viz-s8)]/50"
      : g === "conditional" ? "text-[var(--viz-s1)] border-[var(--viz-s1)]/50"
        : "text-muted-foreground border-border";
  const icon = g === "robust" || g === "supported" ? "●" : g === "contradicted" || g === "invalid" ? "✕" : g === "not_computed" ? "○" : "◐";
  return <span className={cn("rounded border px-1.5 py-px text-[10px] font-medium", tone)}>{icon} {g.replace("_", " ")}</span>;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
      <div className="flex max-w-md items-start gap-2"><IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div>{children}</div></div>
    </div>
  );
}

/**
 * Universal frame for every analytical visualization (charts and result tables): stable ID, research
 * question, data class, an always-present information button driven by the central registry, provenance,
 * optional table view, derived-data export, deep link and honest empty/unavailable state.
 */
export function VisualizationFrame({ id, title, question, children, runId, cls, definition, block, table, className, footnote, empty,
  instance, prov, selection }: {
  id: string; title?: string; question?: React.ReactNode; children?: React.ReactNode; runId?: string | null; cls?: DataClass;
  definition?: React.ReactNode; block?: string; table?: () => React.ReactNode; className?: string; footnote?: React.ReactNode;
  empty?: React.ReactNode | null; instance?: string; prov?: Provenance; selection?: Record<string, string | number | null | undefined>;
}) {
  const [showTable, setShowTable] = useState(false);
  const ref = useRef<HTMLElement>(null);
  const ctx = useProvenance();
  const entry = vizEntry(id);
  const p: Provenance = { ...ctx, ...prov, runId: runId ?? prov?.runId ?? ctx.runId };
  const klass: DataClass = empty ? "unavailable" : cls ?? p.dataClass ?? "model_generated";
  const t = title ?? entry?.title ?? id;
  const domId = instance ? id + "--" + instance : id;
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" && !entry) console.error("Visualization " + id + " has no registry entry");
    if (typeof window !== "undefined" && window.location.hash === "#" + id && ref.current) ref.current.scrollIntoView({ block: "start" });
  }, [entry, id]);
  return (
    <section ref={ref} id={domId} data-viz-id={id} data-viz-kind={entry?.kind ?? "chart"} aria-labelledby={domId + "-t"}
      className={cn("flex min-w-0 scroll-mt-20 flex-col rounded-xl border border-border bg-card p-4", className)}>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] text-muted-foreground">{id}</span>
            <h3 id={domId + "-t"} className="text-sm font-semibold">{t}</h3>
            <DataTag cls={klass} />
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">{question ?? entry?.researchQuestion}</p>
        </div>
        <div className="flex items-center gap-1 text-muted-foreground">
          <VisualizationInfo id={id} title={t} entry={entry} prov={{ ...p, dataClass: klass }} note={definition} selection={selection} />
          {table && !empty ? (
            <button aria-label={showTable ? "Show chart" : "Show table"} aria-pressed={showTable} onClick={() => setShowTable(!showTable)} className="rounded p-1 hover:bg-muted">
              {showTable ? <IconChartBar className="h-4 w-4" /> : <IconTable className="h-4 w-4" />}
            </button>
          ) : null}
          {p.runId && !empty ? (
            <a aria-label="Export derived data (CSV)" className="rounded p-1 hover:bg-muted" href={exportUrl(p.runId, "csv", block)}><IconDownload className="h-4 w-4" /></a>
          ) : null}
          <a aria-label={"Link to " + id} href={"#" + id} className="rounded p-1 hover:bg-muted"><IconLink className="h-4 w-4" /></a>
        </div>
      </div>
      <div className="min-w-0 flex-1">
        {empty ? <Empty>{empty}</Empty> : showTable && table ? <div className="max-h-96 overflow-auto">{table()}</div> : children}
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <span>{footnote}</span>
        {p.runId ? <span className="font-mono">run {shortId(p.runId)}</span> : null}
      </div>
    </section>
  );
}

/** Short alias used throughout the page components. */
export const Viz = VisualizationFrame;

export function dataClassOf(res: any): DataClass {
  const c = res?.universe?.data_class;
  if (c === "observed") return "observed";
  if (res?.warnings?.some?.((w: string) => w.includes("SYNTHETIC"))) return "illustrative";
  return "model_generated";
}
