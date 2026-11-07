"use client";
import { useState, useSyncExternalStore } from "react";
import { toast } from "sonner";
import { IconAlertTriangle, IconDownload, IconInfoCircle, IconPlayerPlay, IconTable, IconChartBar } from "@tabler/icons-react";
import { Tooltip } from "@/components/ui/tooltip-card";
import { AnimatedTabBar } from "@/components/ui/animated-tabs";
import { InlineProgress } from "@/components/experiment/RunProgress";
import { HoverBorderGradient } from "@/components/ui/hover-border-gradient";
import { exportUrl, submitStudy, useInvalidateStudy, useStudyDefaults, useStudyLatest, type StudyEnvelope, type StudyKind } from "@/lib/api/v2";
import { shortId } from "@/lib/format";
import { cn } from "@/lib/utils";

/* eslint-disable @typescript-eslint/no-explicit-any */
export type DataClass = "observed" | "model_generated" | "illustrative" | "unavailable";
export type EvidenceGrade = "robust" | "conditional" | "diagnostic" | "fragile" | "not_computed" | "contradicted" | "invalid" | "supported";

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

/** Standard visualization frame: id, question, data class, run provenance, definition tooltip, export, table toggle. */
export function Viz({ id, title, question, children, runId, cls = "model_generated", definition, block, table, className,
  footnote, empty }: {
  id: string; title: string; question?: React.ReactNode; children?: React.ReactNode; runId?: string | null; cls?: DataClass;
  definition?: React.ReactNode; block?: string; table?: () => React.ReactNode; className?: string; footnote?: React.ReactNode;
  empty?: React.ReactNode | null;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section id={id} className={cn("flex min-w-0 flex-col rounded-xl border border-border bg-card p-4", className)} aria-labelledby={id + "-t"}>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] text-muted-foreground">{id}</span>
            <h3 id={id + "-t"} className="text-sm font-semibold">{title}</h3>
            <DataTag cls={empty ? "unavailable" : cls} />
          </div>
          {question ? <p className="mt-0.5 text-xs text-muted-foreground">{question}</p> : null}
        </div>
        <div className="flex items-center gap-1 text-muted-foreground">
          {definition ? (
            <Tooltip content={<div className="max-w-xs text-xs leading-relaxed">{definition}</div>}>
              <button aria-label={"Why: definition of " + title} className="rounded p-1 hover:bg-muted"><IconInfoCircle className="h-4 w-4" /></button>
            </Tooltip>
          ) : null}
          {table && !empty ? (
            <button aria-label="Toggle table view" onClick={() => setShowTable(!showTable)} className="rounded p-1 hover:bg-muted">
              {showTable ? <IconChartBar className="h-4 w-4" /> : <IconTable className="h-4 w-4" />}
            </button>
          ) : null}
          {runId && !empty ? (
            <a aria-label="Export derived data (CSV)" className="rounded p-1 hover:bg-muted" href={exportUrl(runId, "csv", block)}>
              <IconDownload className="h-4 w-4" />
            </a>
          ) : null}
        </div>
      </div>
      <div className="min-w-0 flex-1">
        {empty ? <Empty>{empty}</Empty> : showTable && table ? <div className="max-h-96 overflow-auto">{table()}</div> : children}
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <span>{footnote}</span>
        {runId ? <span className="font-mono">run {shortId(runId)}</span> : null}
      </div>
    </section>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
      <div className="flex max-w-md items-start gap-2"><IconAlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div>{children}</div></div>
    </div>
  );
}

export function DataTable({ columns, rows, className }: { columns: { key: string; label: string; fmt?: (v: any, r: any) => React.ReactNode }[];
  rows: any[]; className?: string }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const mounted = useMounted();
  if (!mounted) rows = [];  // rows come from client-side queries: render them after hydration only
  const sorted = sort ? [...rows].sort((a, b) => {
    const x = a[sort.key], y = b[sort.key];
    if (x === y) return 0;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * sort.dir;
  }) : rows;
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            {columns.map((c) => (
              <th key={c.key} className="cursor-pointer whitespace-nowrap px-2 py-1.5 font-medium"
                onClick={() => setSort({ key: c.key, dir: sort?.key === c.key && sort.dir === 1 ? -1 : 1 })}>
                {c.label}{sort?.key === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={i} className="border-b border-border/50 hover:bg-muted/40">
              {columns.map((c) => <td key={c.key} className="whitespace-nowrap px-2 py-1">{c.fmt ? c.fmt(r[c.key], r) : fmtCell(r[c.key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function fmtCell(v: any): React.ReactNode {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") return Number.isInteger(v) || Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toFixed(4);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Looks up the latest completed run of a study. Never launches computation on view: the user clicks Run. */
export function StudyGate({ kind, title, description, children, specOverride, runLabel }: {
  kind: StudyKind; title: string; description?: React.ReactNode; children: (env: StudyEnvelope) => React.ReactNode;
  specOverride?: any; runLabel?: string;
}) {
  const latest = useStudyLatest(kind);
  const defaults = useStudyDefaults(kind);
  const invalidate = useInvalidateStudy();
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
  const header = (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-muted/20 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
        <span className="font-medium text-foreground">{title}</span>
        <span>study <span className="font-mono">{kind}</span></span>
        {env?.run_id ? <span className="font-mono">run {shortId(env.run_id)}</span> : null}
        {env?.catalog_hash ? <span className="font-mono">catalog {String(env.catalog_hash).slice(0, 8)}</span> : null}
        {env?.finished_at ? <span>finished {env.finished_at.replace("T", " ").slice(0, 16)} UTC</span> : null}
        {env?.experiments ? <span>{env.experiments}</span> : null}
      </div>
      <div className="flex items-center gap-2">
        <button className="rounded border border-border px-2 py-1 hover:bg-muted" onClick={() => {
          setText(JSON.stringify(env?.spec ?? defaults.data?.spec ?? {}, null, 2));
          setEditing(!editing);
        }}>{editing ? "Close spec" : "Edit spec"}</button>
        <button className="flex items-center gap-1 rounded border border-border px-2 py-1 hover:bg-muted" onClick={() => run(false)}>
          <IconPlayerPlay className="h-3 w-3" /> {runLabel ?? "Run default"}
        </button>
      </div>
    </div>
  );
  const editor = editing ? (
    <div className="mb-4 rounded-lg border border-border p-3">
      <div className="mb-2 text-xs text-muted-foreground">Canonical study spec (validated server-side; the run ID is the SHA-256 of this JSON plus the data catalog hash). Submit runs only on click.</div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} className="h-72 w-full rounded border border-input bg-transparent p-2 font-mono text-[11px]" />
      <div className="mt-2 flex gap-2">
        <button className="rounded border border-border px-3 py-1 text-xs hover:bg-muted" onClick={() => {
          try { const s = JSON.parse(text); if (s.data) s.data.catalog_hash = null; void run(false, s); setEditing(false); } catch (e) { toast.error("Invalid JSON: " + (e as Error).message); }
        }}>Submit spec</button>
        <button className="rounded border border-border px-3 py-1 text-xs hover:bg-muted" onClick={() => setText(JSON.stringify(defaults.data?.spec ?? {}, null, 2))}>Reset to defaults</button>
      </div>
    </div>
  ) : null;
  let body: React.ReactNode;
  if (latest.isLoading) body = <div className="h-96 animate-pulse rounded-xl bg-muted/40" />;
  else if (latest.isError) body = <Empty>API unreachable: {String((latest.error as Error)?.message)}. Start it with <code>make api</code>.</Empty>;
  else if (!env || env.status === "none") body = (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border py-14 text-center text-sm text-muted-foreground">
      <span>Results not computed. No persisted run of this study exists yet{description ? ":" : "."}</span>
      {description ? <span className="max-w-xl text-xs">{description}</span> : null}
      <HoverBorderGradient onClick={() => run(false)} containerClassName="rounded-full" className="bg-background px-5 py-2 text-sm text-foreground">Run this study</HoverBorderGradient>
      <span className="text-xs">or from the CLI: <code>python -m lifecycle.cli seed-v2 --only {kind}</code></span>
    </div>
  );
  else if (env.status === "failed") body = (
    <div className="space-y-3">
      <Empty>
        <div className="font-medium text-foreground">Study failed — no figures are shown from a failed run.</div>
        <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-left text-[11px]">{(env.error ?? "").split("\n").slice(0, 6).join("\n")}</pre>
        {(env.error ?? "").includes("IncompatibleUniverse") ? <div className="mt-2">This is a data-entitlement or coverage limit, not a bug. Edit the spec to use another universe, or ingest the missing series (WRDS).</div> : null}
      </Empty>
    </div>
  );
  else if (env.status !== "done") body = (
    <div className="rounded-xl border border-border p-6"><InlineProgress stage={env.stage ?? env.status} progress={env.progress ?? 0} />
      <div className="mt-2 text-xs text-muted-foreground">Real backend progress (registry-polled). The page updates when the run finishes.</div></div>
  );
  else body = children(env);
  return <div>{header}{editor}{body}</div>;
}

export function Warnings({ items }: { items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="mb-4 space-y-1 rounded-lg border border-[var(--viz-s4)]/40 bg-[var(--viz-s4)]/5 px-3 py-2 text-xs">
      {items.map((w) => <div key={w} className="flex gap-2"><IconAlertTriangle className="h-3.5 w-3.5 shrink-0 text-[var(--viz-s4)]" /><span>{w}</span></div>)}
    </div>
  );
}

export function ContextBar({ items }: { items: [string, React.ReactNode][] }) {
  return (
    <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-3 py-2 text-[11px]" role="status">
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

export function dataClassOf(res: any): DataClass {
  const c = res?.universe?.data_class;
  if (c === "observed") return "observed";
  if (res?.warnings?.some?.((w: string) => w.includes("SYNTHETIC"))) return "illustrative";
  return "model_generated";
}

/** Aceternity animated pill tabs, controlled; only the active panel is mounted. */
export function PageTabs({ tabs, initial }: { tabs: { title: string; value: string; content: React.ReactNode }[]; initial?: string }) {
  const [v, setV] = useState(initial ?? tabs[0].value);
  return (
    <div>
      <AnimatedTabBar className="mb-4" value={v} onChange={setV} tabs={tabs.map((t) => ({ title: t.title, value: t.value }))} />
      {tabs.find((t) => t.value === v)?.content}
    </div>
  );
}

const noopSubscribe = () => () => undefined;
function useMounted() {
  return useSyncExternalStore(noopSubscribe, () => true, () => false);
}
