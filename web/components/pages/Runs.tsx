"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Timeline } from "@/components/ui/timeline";
import { TracingBeam } from "@/components/ui/tracing-beam";
import { Badge } from "@/components/ui/badge";
import { PageHeader, Section } from "@/components/common/Section";
import { Field, NativeSelect } from "@/components/common/Fields";
import { ResultSummary } from "@/components/experiment/ResultSummary";
import { Provenance } from "@/components/experiment/Provenance";
import { reportUrl } from "@/lib/api/client";
import { useResults, useRunStatus, useRuns } from "@/lib/api/hooks";
import type { RunRow } from "@/lib/api/types";
import { shortId, signedPct, usd } from "@/lib/format";

function statusBadge(s: string) {
  if (s === "done") return <Badge variant="secondary">done</Badge>;
  if (s === "failed") return <Badge variant="destructive">failed</Badge>;
  return <Badge variant="outline">{s}</Badge>;
}

function RunDetail({ id }: { id: string }) {
  const st = useRunStatus(id);
  const res = useResults(id, st.data?.status === "done" && st.data?.kind === "experiment");
  const d = st.data;
  if (!d) return <div className="h-64 animate-pulse rounded-xl bg-muted/40" />;
  return (
    <TracingBeam className="px-2">
      <div className="space-y-4">
        <Section title={<span className="flex items-center gap-2">{d.label ?? d.kind} {statusBadge(d.status)}</span>}
          description={`created ${d.created_at} · finished ${d.finished_at ?? "–"} · stage ${d.stage}`}
          actions={<div className="flex gap-2 text-xs">
            {(["pdf", "csv", "bibtex", "json"] as const).map((f) => (
              <a key={f} href={reportUrl(id, f)} className="rounded-md border border-border px-2 py-1 hover:bg-muted">{f.toUpperCase()}</a>
            ))}
          </div>}>
          <Provenance meta={st.data as unknown as Record<string, unknown>} runId={id} />
          <div className="mt-2 text-xs text-muted-foreground">Reproduce bit-for-bit: <code className="rounded bg-muted px-1">make reproduce RUN={id}</code></div>
          {d.kind === "sweep" ? <div className="mt-2 text-sm"><Link className="underline" href="/withdrawal-lab">Open in the Withdrawal Lab →</Link></div> : null}
          {d.kind === "compare" ? <div className="mt-2 text-sm"><Link className="underline" href={"/compare?id=" + id}>Open comparison →</Link></div> : null}
          {d.error ? <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-destructive">{d.error}</pre> : null}
        </Section>
        <Section title="Experiment specification" description="Canonical JSON; its SHA-256 (with the catalog hash) is the run ID.">
          <pre className="max-h-[420px] overflow-auto rounded-lg bg-muted/40 p-3 text-[11px] leading-relaxed">{JSON.stringify(d.spec, null, 2)}</pre>
        </Section>
        {d.timings ? (
          <Section title="Timings & warnings">
            <div className="flex flex-wrap gap-2 text-xs">
              {Object.entries(d.timings).map(([k, v]) => <Badge key={k} variant="outline">{k} {Number(v).toFixed(2)}s</Badge>)}
              {(d.warnings ?? []).map((w) => <Badge key={w} variant="outline">⚠ {w}</Badge>)}
            </div>
          </Section>
        ) : null}
        {res.data ? <ResultSummary r={res.data.results} runId={id} compact /> : null}
      </div>
    </TracingBeam>
  );
}

export function Runs() {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("id");
  const [kind, setKind] = useState("");
  const runs = useRuns(kind || undefined, 150);
  const rows: RunRow[] = runs.data?.runs ?? [];
  const byDay = new Map<string, RunRow[]>();
  for (const r of rows) {
    const day = r.created_at.slice(0, 10);
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(r);
  }
  return (
    <div>
      <PageHeader title="Runs & Reports" description="Audit trail of every computation: spec hash, data catalog hash, engine version, status and exports.">
        <Field label="Kind"><NativeSelect value={kind} onChange={setKind} options={[{ value: "", label: "All" }, { value: "experiment", label: "Experiments" },
          { value: "sweep", label: "Sweeps" }, { value: "compare", label: "Comparisons" }, { value: "validation", label: "Validations" },
          { value: "attribution", label: "Attribution" }, { value: "hypotheses", label: "Hypotheses" }]} /></Field>
      </PageHeader>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,460px)_minmax(0,1fr)]">
        <div className="min-w-0">
          <Timeline data={[...byDay.entries()].map(([day, list]) => ({
            title: day,
            content: (
              <div className="space-y-2">
                {list.map((r) => (
                  <button key={r.run_id} onClick={() => router.push("/runs?id=" + r.run_id)}
                    className={"w-full rounded-lg border p-2 text-left text-xs " + (id === r.run_id ? "border-[var(--viz-s1)] bg-muted/50" : "border-border hover:bg-muted/40")}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium">{r.label ?? (r.summary?.policy as string) ?? r.kind}</span>
                      {statusBadge(r.status)}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 font-mono text-[10px] text-muted-foreground">
                      <span>{r.kind}</span><span>run {shortId(r.run_id)}</span><span>spec {shortId(r.spec_hash)}</span>
                      <span>cat {String(r.catalog_hash).slice(0, 8)}</span><span>{r.created_at.slice(11, 19)}</span>
                    </div>
                    {r.summary && typeof r.summary.ce === "number" ? (
                      <div className="mt-1 tabular-nums text-muted-foreground">CE {usd(r.summary.ce as number)}{typeof r.summary.delta === "number" ? " · ΔCE " + signedPct(r.summary.delta as number) : ""}</div>
                    ) : null}
                  </button>
                ))}
              </div>
            ),
          }))} />
          {rows.length === 0 ? <div className="text-sm text-muted-foreground">No runs yet.</div> : null}
        </div>
        <div className="min-w-0">{id ? <RunDetail id={id} /> : <Section><div className="py-16 text-center text-sm text-muted-foreground">Select a run from the timeline.</div></Section>}</div>
      </div>
    </div>
  );
}
