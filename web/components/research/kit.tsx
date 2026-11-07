"use client";
import { useState } from "react";
import { toast } from "sonner";
import { IconAlertTriangle, IconPlayerPlay, IconAdjustments } from "@tabler/icons-react";
import { InlineProgress } from "@/components/experiment/RunProgress";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";
import { submitStudy, useInvalidateStudy, useStudyDefaults, useStudyLatest, type StudyEnvelope, type StudyKind } from "@/lib/api/v2";
import { shortId } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useResearchContext } from "@/lib/store";
import { studySpecFromContext } from "@/lib/research/context";
import { ProvenanceProvider, provenanceFromStudy } from "@/components/visualizations/provenance";
import { Empty } from "@/components/visualizations/VisualizationFrame";

export { DataTag, GradeTag, Viz, VisualizationFrame, Empty, dataClassOf, type DataClass } from "@/components/visualizations/VisualizationFrame";
export { DataTable, ResearchTable } from "@/components/visualizations/ResearchTable";

/* eslint-disable @typescript-eslint/no-explicit-any */
export type EvidenceGrade = "robust" | "conditional" | "diagnostic" | "fragile" | "not_computed" | "contradicted" | "invalid" | "supported";

/**
 * Looks up the latest completed run of a study and provides its provenance to every visualization inside.
 * Never launches computation on view: the user clicks "Run default" or "Run with current assumptions"
 * (the shared research context mapped onto this study's spec). Identical specs hit the cache.
 */
export function StudyGate({ kind, title, description, children, specOverride, runLabel }: {
  kind: StudyKind; title: string; description?: React.ReactNode; children: (env: StudyEnvelope) => React.ReactNode;
  specOverride?: any; runLabel?: string;
}) {
  const latest = useStudyLatest(kind);
  const defaults = useStudyDefaults(kind);
  const invalidate = useInvalidateStudy();
  const ctx = useResearchContext();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState<string>("");
  const env = latest.data;
  async function run(force = false, spec?: any) {
    try {
      const r = await submitStudy(kind, spec ?? specOverride ?? {}, force);
      toast.success(r.status === "done" ? "Cached result found (identical spec hash)" : "Study queued — progress streams from the backend");
      invalidate(kind);
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }
  function runWithContext() {
    const { spec, notes } = studySpecFromContext(kind, ctx);
    notes.forEach((n) => toast.message(n));
    void run(false, spec);
  }
  const header = (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/20 px-3 py-2 text-xs" data-study={kind}>
      <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
        <span className="font-medium text-foreground">{title}</span>
        <span>study <span className="font-mono">{kind}</span></span>
        {env?.run_id ? <span className="font-mono">run {shortId(env.run_id)}</span> : null}
        {env?.catalog_hash ? <span className="font-mono">catalog {String(env.catalog_hash).slice(0, 8)}</span> : null}
        {env?.finished_at ? <span>finished {env.finished_at.replace("T", " ").slice(0, 16)} UTC</span> : null}
        {env?.experiments ? <span>{env.experiments}</span> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className="rounded border border-border px-2 py-1 hover:bg-muted" onClick={() => {
          setText(JSON.stringify(env?.spec ?? defaults.data?.spec ?? {}, null, 2));
          setEditing(!editing);
        }}>{editing ? "Close spec" : "Edit spec"}</button>
        <button className="flex items-center gap-1 rounded border border-border px-2 py-1 hover:bg-muted" onClick={runWithContext}
          title="Builds this study's spec from the shared research context (investor, scenario, preferences, costs, withdrawal)">
          <IconAdjustments className="h-3 w-3" /> Run with current assumptions
        </button>
        <button className="flex items-center gap-1 rounded border border-border px-2 py-1 hover:bg-muted" onClick={() => run(false)}>
          <IconPlayerPlay className="h-3 w-3" /> {runLabel ?? "Run default"}
        </button>
      </div>
    </div>
  );
  const editor = editing ? (
    <div className="mb-4 rounded-lg border border-border p-3">
      <div className="mb-2 text-xs text-muted-foreground">Canonical study spec (validated server-side; the run ID is the SHA-256 of this JSON plus the data catalog hash). Submit runs only on click.</div>
      <textarea aria-label="Study specification JSON" value={text} onChange={(e) => setText(e.target.value)} className="h-72 w-full rounded border border-input bg-transparent p-2 font-mono text-[11px]" />
      <div className="mt-2 flex flex-wrap gap-2">
        <button className="rounded border border-border px-3 py-1 text-xs hover:bg-muted" onClick={() => {
          try { const s = JSON.parse(text); if (s.data) s.data.catalog_hash = null; void run(false, s); setEditing(false); } catch (e) { toast.error("Invalid JSON: " + (e as Error).message); }
        }}>Submit spec</button>
        <button className="rounded border border-border px-3 py-1 text-xs hover:bg-muted" onClick={() => setText(JSON.stringify(defaults.data?.spec ?? {}, null, 2))}>Reset to defaults</button>
        <button className="rounded border border-border px-3 py-1 text-xs hover:bg-muted" onClick={() => setText(JSON.stringify(studySpecFromContext(kind, ctx).spec, null, 2))}>Load current assumptions</button>
      </div>
    </div>
  ) : null;
  let body: React.ReactNode;
  if (latest.isLoading) body = <div className="h-96 animate-pulse rounded-xl bg-muted/40" />;
  else if (latest.isError) body = <Empty>API unreachable: {String((latest.error as Error)?.message)}. Start it with <code>make api</code>.</Empty>;
  else if (!env || env.status === "none") body = (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border py-14 text-center text-sm text-muted-foreground" data-study-state="not-computed">
      <span>Results not computed. No persisted run of this study exists yet{description ? ":" : "."}</span>
      {description ? <span className="max-w-xl text-xs">{description}</span> : null}
      <HoverBorderGradient onClick={() => run(false)} containerClassName="rounded-full" className="bg-background px-5 py-2 text-sm text-foreground">Run this study</HoverBorderGradient>
      <span className="text-xs">or from the CLI: <code>python -m lifecycle.cli seed-v2 --only {kind}</code></span>
    </div>
  );
  else if (env.status === "failed") body = (
    <Empty>
      <div className="font-medium text-foreground">Study failed — no figures are shown from a failed run.</div>
      <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-left text-[11px]">{(env.error ?? "").split("\n").slice(0, 6).join("\n")}</pre>
      {(env.error ?? "").includes("IncompatibleUniverse") ? <div className="mt-2">This is a data-entitlement or coverage limit, not a bug. Edit the spec to use another universe, or ingest the missing series (WRDS).</div> : null}
    </Empty>
  );
  else if (env.status !== "done") body = (
    <div className="rounded-xl border border-border p-6"><InlineProgress stage={env.stage ?? env.status} progress={env.progress ?? 0} />
      <div className="mt-2 text-xs text-muted-foreground">Real backend progress (registry-polled). The page updates when the run finishes.</div></div>
  );
  else body = <ProvenanceProvider value={provenanceFromStudy(env)}>{children(env)}</ProvenanceProvider>;
  return <div>{header}{editor}{body}</div>;
}

export function Warnings({ items }: { items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mb-4 space-y-1 rounded-lg border border-[var(--viz-s4)]/40 bg-[var(--viz-s4)]/5 px-3 py-2 text-xs" role="note">
      {items.map((w) => <div key={w} className="flex gap-2"><IconAlertTriangle className="h-3.5 w-3.5 shrink-0 text-[var(--viz-s4)]" /><span>{w}</span></div>)}
    </div>
  );
}

export function ContextBar({ items }: { items: [string, React.ReactNode][] }) {
  return (
    <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-3 py-2 text-[11px]" role="status" aria-label="Run context">
      {items.map(([k, v]) => (
        <span key={k} className="whitespace-nowrap"><span className="text-muted-foreground">{k}</span> <span className="font-medium">{v ?? "–"}</span></span>
      ))}
    </div>
  );
}

export function Grid({ children, cols = 2 }: { children: React.ReactNode; cols?: 1 | 2 | 3 }) {
  return <div className={cn("grid gap-4", cols === 2 && "lg:grid-cols-2", cols === 3 && "md:grid-cols-2 xl:grid-cols-3")}>{children}</div>;
}

export function Kpi({ label, value, sub, ci }: { label: React.ReactNode; value: React.ReactNode; sub?: React.ReactNode; ci?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-3">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tabular-nums">{value}</div>
      {ci ? <div className="text-[11px] tabular-nums text-muted-foreground">{ci}</div> : null}
      {sub ? <div className="text-[11px] text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

export function Seg<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label?: string }) {
  return (
    <div className="flex flex-wrap items-center gap-1 text-xs" role="radiogroup" aria-label={label}>
      {label ? <span className="mr-1 text-muted-foreground">{label}</span> : null}
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}
          className={cn("rounded-md border px-2 py-0.5", o.value === value ? "border-foreground/40 bg-foreground/10" : "border-border text-muted-foreground hover:bg-muted")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
