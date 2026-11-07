"use client";
import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ResearchPage, Sec } from "@/components/research/page";
import { RunHistory } from "@/components/research/runs/RunHistory";
import { DataTable, Empty, Grid, GradeTag, Kpi, Viz } from "@/components/research/kit";
import { API_BASE, apiPost, eventsUrl, reportUrl } from "@/lib/api/client";
import { exportUrl, useV2 } from "@/lib/api/v2";

/* eslint-disable @typescript-eslint/no-explicit-any */
const STUDY_KINDS = ["frontier", "signed_flow", "permanent", "rebalance", "scenario_lab", "asof", "optimize", "compare_v2", "evidence", "multi_asset", "historical_replay"];
const STAGES = ["queued", "generating_scenarios", "simulating", "optimising", "uncertainty", "robustness", "summarising", "done"];

function LiveProgress({ runId, kind, spec }: { runId: string; kind: string; spec: any }) {
  const [events, setEvents] = useState<{ stage: string; fraction: number; at: string; status: string }[]>([]);
  useEffect(() => {
    const src = new EventSource(eventsUrl(runId));
    src.onmessage = (e) => {
      try {
        const p = JSON.parse(e.data);
        setEvents((ev) => [...ev, { stage: p.stage, fraction: p.fraction, status: p.status, at: new Date().toISOString().slice(11, 19) }]);
        if (["done", "failed", "cancelled"].includes(p.status)) src.close();
      } catch { /* ignore keep-alive */ }
    };
    src.onerror = () => src.close();
    return () => src.close();
  }, [runId]);
  const last = events[events.length - 1];
  async function cancel() { await apiPost("/v1/experiments/" + runId + "/cancel", {}); toast.message("Cancellation requested"); }
  async function retry() {
    if (!STUDY_KINDS.includes(kind)) { toast.error("Retry from the page that owns this run kind"); return; }
    const s = { ...spec }; if (s.data) s.data = { ...s.data, catalog_hash: null };
    await apiPost("/v1/studies/" + kind + "?force=true", s); toast.success("Re-submitted (forced)");
  }
  return (
    <div className="space-y-2 text-xs">
      <div className="flex flex-wrap gap-1">{STAGES.map((s) => <span key={s} className={"rounded border px-1.5 py-0.5 " + (last?.stage === s ? "border-foreground/50 bg-foreground/10" : events.some((e) => e.stage === s) ? "border-border text-foreground" : "border-border text-muted-foreground")}>{s.replace("_", " ")}</span>)}</div>
      <div className="text-muted-foreground">{last ? last.status + " · " + last.stage + " · " + Math.round((last.fraction ?? 0) * 100) + "%" : "connecting to the backend SSE stream…"}</div>
      <div className="max-h-32 overflow-auto font-mono text-[10px] text-muted-foreground">{events.map((e, i) => <div key={i}>{e.at} {e.status} {e.stage} {(e.fraction * 100).toFixed(0)}%</div>)}</div>
      <div className="flex gap-2"><button onClick={cancel} className="rounded border border-border px-2 py-1 hover:bg-muted">Cancel</button><button onClick={retry} className="rounded border border-border px-2 py-1 hover:bg-muted">Retry (force)</button></div>
    </div>
  );
}

function Body() {
  const params = useSearchParams();
  const runs = useV2<any>("/v1/runs", { limit: 300 }, { refetch: 10_000 });
  const router = useRouter();
  const sel = params.get("id");
  const setSel = (id: string) => {
    const q = new URLSearchParams(params.toString());
    q.set("id", id);
    router.replace("/runs?" + q.toString(), { scroll: false });
  };
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const ins = useV2(sel ? "/v1/runs/" + sel + "/inspect" : null);
  const figs = useV2("/v1/results/figures", undefined, { refetch: 15_000 });
  const health = useV2("/v1/data/health");
  const paper = useV2("/v1/paper/preview");
  const audit = useV2("/v1/audit", { limit: 300 }, { refetch: 10_000 });
  const health0 = useV2<any>("/health");
  const comp = useV2(a && b ? "/v1/runs/compatibility" : null, { a, b });
  const cacheHits = new Set((audit.data?.events ?? []).filter((e: any) => e.action === "cache_hit").map((e: any) => e.run_id));
  const rows = (runs.data?.runs ?? []).map((r: any) => ({ ...r, cache: cacheHits.has(r.run_id) }));
  const d = ins.data;
  const stale = d && health0.data && (d.catalog_hash !== health0.data.data?.catalog_hash);
  async function build() {
    const r = await apiPost<any>("/v1/reports/build", []);
    toast.success("Report manifest built for " + r.manifest.length + " runs");
  }
  return (
    <div className="space-y-4">
      <Sec id="registry">
      <Viz id="RN-01" title="Run registry" question="Every persisted run: status, kind, parent, data vintage, policy, timestamps, cache hits and failure reasons. Click a row ID to inspect." cls="observed"
        definition="Run ID = SHA-256 of the canonical spec + data catalog hash. Identical specs hit the cache.">
        <div className="max-h-96 overflow-auto"><DataTable rows={rows} columns={[{ key: "run_id", label: "run", fmt: (v) => <button className="font-mono underline" onClick={() => setSel(v)}>{v.slice(0, 10)}</button> },
          { key: "kind", label: "type" }, { key: "semantics", label: "engine semantics" }, { key: "status", label: "status" }, { key: "label", label: "label" }, { key: "parent_id", label: "parent", fmt: (v) => (v ? v.slice(0, 8) : "–") },
          { key: "catalog_hash", label: "data vintage", fmt: (v) => (v ? String(v).slice(0, 8) : "–") }, { key: "summary", label: "policy / summary", fmt: (v) => (v ? String(v.policy ?? v.universe ?? JSON.stringify(v).slice(0, 60)) : "–") },
          { key: "created_at", label: "created" }, { key: "finished_at", label: "finished" }, { key: "cache", label: "cache hit" }, { key: "error", label: "error", fmt: (v) => (v ? String(v).split("\n")[0].slice(0, 80) : "") }]} /></div>
      </Viz>
      </Sec>
      <Sec id="registry"><Grid>
        <Viz id="RN-02" title="Run inspector" question={sel ? "Run " + sel : "Select a run in the registry."} cls="observed" empty={sel ? null : "No run selected."}>
          {d ? <div className="space-y-2 text-xs">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3"><Kpi label="kind / status" value={d.kind} sub={d.status} /><Kpi label="engine (git SHA)" value={d.engine_version} sub={"lock " + d.lock_hash} />
              <Kpi label="catalog" value={String(d.catalog_hash).slice(0, 12)} sub={d.data_class ?? d.raw_or_derived} /></div>
            <div>seeds: {JSON.stringify(d.seeds)} · warnings: {(d.warnings ?? []).join("; ") || "none"}</div>
            <details open><summary className="cursor-pointer text-muted-foreground">canonical spec JSON</summary><pre className="max-h-72 overflow-auto rounded border border-border p-2 text-[10px]">{JSON.stringify(d.spec, null, 2)}</pre></details>
            {d.universe?.provenance ? <DataTable rows={Object.entries(d.universe.provenance).map(([k, v]: any) => ({ k, ...v }))} columns={[{ key: "k", label: "asset" }, { key: "provenance", label: "raw/derived" }, { key: "source", label: "source" }, { key: "licence_class", label: "licence" }]} /> : null}
          </div> : sel ? <div className="h-40 animate-pulse rounded bg-muted/40" /> : null}
        </Viz>
        <Viz id="RN-03" title="Real execution progress" question="Backend SSE stages for the selected run (ingestion where relevant, fitting, simulation, uncertainty, summarising), with cancel / retry." cls="observed" empty={sel ? null : "Select a run."}>
          {sel && d ? <LiveProgress key={sel} runId={sel} kind={d.kind} spec={d.spec} /> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="figures"><Grid>
        <Viz id="RN-04" title="Figure gallery (F1–F6)" question="Flagship exhibits with their supporting run IDs, status and evidence grade." cls="observed">
          {figs.data ? <div className="grid gap-2 md:grid-cols-2">{figs.data.figures.map((f: any) => (
            <a key={f.figure} href={f.page} className="rounded-lg border border-border p-3 text-xs hover:bg-muted/40">
              <div className="flex items-center justify-between"><b>{f.figure} · {f.title}</b><GradeTag grade={f.evidence_grade} /></div>
              <div className="mt-1 text-muted-foreground">study {f.study} · {f.run_id ? "run " + f.run_id.slice(0, 10) + " · " + (f.finished_at ?? "") : f.status}</div>
              {f.failure ? <div className="mt-1 text-[var(--viz-s8)]">{f.failure.split("\n")[0]}</div> : null}
              <code className="mt-1 block text-[10px]">{f.reproduce}</code>
            </a>))}</div> : null}
        </Viz>
        <Viz id="RN-09" title="Paper build preview" question="Sections, missing figures, bibliography coverage and LaTeX tool availability for paper/main.tex." cls="observed">
          {paper.data ? <div className="space-y-1 text-xs">
            <div>Sections: {paper.data.sections.join(" · ")}</div>
            <div className={paper.data.missing_figures.length ? "text-[var(--viz-s4)]" : ""}>Missing figures: {paper.data.missing_figures.join(", ") || "none"}</div>
            <div>Bibliography: {paper.data.bib_entries} entries · cited {paper.data.cited.length} · undefined citations {paper.data.undefined_citations.join(", ") || "none"} · uncited {paper.data.uncited.length}</div>
            <div>latexmk available: {String(paper.data.latexmk_available)} · run_ids.json present: {String(paper.data.run_ids_file)}</div>
            <code className="block rounded border border-border p-2">{paper.data.build}</code></div> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="reproduce"><Grid>
        <Viz id="RN-05" title="Compare saved runs" question="Checks compatibility (kind, catalog, universe, generator, seeds, horizon, spending) and explains any rejection." cls="observed">
          <div className="flex flex-wrap gap-2 text-xs"><input placeholder="run A" value={a} onChange={(e) => setA(e.target.value.trim())} className="h-8 w-44 rounded border border-input bg-transparent px-2 font-mono" />
            <input placeholder="run B" value={b} onChange={(e) => setB(e.target.value.trim())} className="h-8 w-44 rounded border border-input bg-transparent px-2 font-mono" />
            {sel ? <button className="rounded border border-border px-2" onClick={() => (a ? setB(sel) : setA(sel))}>use selected</button> : null}</div>
          {comp.data ? <div className="mt-2 text-xs"><div className="font-medium">{comp.data.compatible ? "✓ compatible — paired comparison allowed" : "✕ not directly comparable"}</div>
            <ul className="list-disc pl-5">{comp.data.reasons.map((x: string) => <li key={x}>{x}</li>)}</ul>{comp.data.remedy ? <div className="text-muted-foreground">Remedy: {comp.data.remedy}</div> : null}
            {comp.data.compatible ? <a className="underline" href="/compare?section=saved-runs">Compare these runs in Strategy Comparison</a> : null}</div> : comp.isError ? <Empty>{String((comp.error as Error).message)}</Empty> : null}
        </Viz>
        <Viz id="RN-06" title="Export center" question="Derived exports with provenance; licence-aware (no raw WRDS rows exist in any export)." cls="observed">
          <div className="flex flex-wrap gap-2 text-xs">
            {sel && d && STUDY_KINDS.includes(d.kind) ? <><a className="rounded border border-border px-2 py-1" href={exportUrl(sel, "json")}>study JSON</a><a className="rounded border border-border px-2 py-1" href={exportUrl(sel, "csv")}>derived CSV</a></> : null}
            {sel && d?.kind === "experiment" ? <><a className="rounded border border-border px-2 py-1" href={reportUrl(sel, "pdf")}>PDF research pack</a><a className="rounded border border-border px-2 py-1" href={reportUrl(sel, "csv")}>CSV</a><a className="rounded border border-border px-2 py-1" href={reportUrl(sel, "json")}>JSON</a></> : null}
            <a className="rounded border border-border px-2 py-1" href={API_BASE + "/v1/results/manifest"}>JSON manifest</a>
            <a className="rounded border border-border px-2 py-1" href={API_BASE + "/v1/methodology/bibtex"}>BibTeX references</a>
            <button className="rounded border border-border px-2 py-1" onClick={build}>Build report manifest (F1–F6)</button>
          </div>
          <div className="mt-2 text-[11px] text-muted-foreground">Figures: use each chart&apos;s camera icon (PNG/SVG via Plotly) or the per-chart CSV download.</div>
        </Viz>
        <Viz id="RN-07" title="Reproduce command" question="Pinned run input and the deterministic re-execution check; flags if data or engine changed since the run." cls="observed" empty={sel ? null : "Select a run."}>
          {d ? <div className="space-y-2 text-xs"><code className="block rounded border border-border p-2">{d.reproduce}</code><code className="block rounded border border-border p-2">make reproduce RUN={sel}</code>
            <div>The command re-executes the stored spec with the same seeds and asserts identical summary statistics (exit 1 on any difference).</div>
            {stale ? <div className="text-[var(--viz-s4)]">⚠ The current data catalog ({health0.data?.data?.catalog_hash}) differs from this run&apos;s ({d.catalog_hash}): a re-run under today&apos;s data produces a new run ID; the stored run stays addressable.</div> : <div className="text-muted-foreground">Data catalog unchanged since this run.</div>}
            {d.engine_version !== health0.data?.engine_version ? <div className="text-[var(--viz-s4)]">⚠ Engine version changed: run {d.engine_version}, server {health0.data?.engine_version}.</div> : null}</div> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="health"><Grid>
        <Viz id="RN-08" title="Coverage / data health logs" question="Ingestion runs, model failures, series with gaps, model-generated series and recorded test results." cls="observed">
          {health.data ? <div className="space-y-2 text-xs">
            <div className="grid grid-cols-3 gap-2"><Kpi label="series" value={health.data.n_series} sub={"catalog " + health.data.catalog_hash} /><Kpi label="model-generated" value={health.data.model_generated.length} sub={health.data.model_generated.join(", ").slice(0, 60)} />
              <Kpi label="tests" value={health.data.tests ? health.data.tests.passed + " passed" : "not recorded"} sub={health.data.tests ? health.data.tests.failed + " failed · " + health.data.tests.at : "python -m lifecycle.cli selftest"} /></div>
            <DataTable rows={health.data.failed_runs} columns={[{ key: "run_id", label: "failed run", fmt: (v) => v.slice(0, 10) }, { key: "kind", label: "kind" }, { key: "error", label: "reason", fmt: (v) => String(v).split("\n")[0] }]} />
          </div> : null}
        </Viz>
        <Viz id="RN-10" title="Audit trail" question="Exact user/worker actions with the affected run; credentials are never recorded." cls="observed">
          <div className="max-h-80 overflow-auto"><DataTable rows={audit.data?.events ?? []} columns={[{ key: "ts", label: "time (UTC)" }, { key: "actor", label: "actor" }, { key: "action", label: "action" },
            { key: "run_id", label: "run", fmt: (v) => (v ? <button className="font-mono underline" onClick={() => setSel(v)}>{v.slice(0, 10)}</button> : "–") }, { key: "detail", label: "detail" }]} /></div>
        </Viz>
      </Grid></Sec>
      <Sec id="registry"><RunHistory /></Sec>
    </div>
  );
}

/** Runs & Reports: one run registry for every kind, reproduction, figures, exports and data health. */
export function Runs() {
  return (
    <ResearchPage page="runs" intro="Every computation in one registry — experiments, sweeps, comparisons, validations, attributions, hypotheses and the nine research studies — with spec and catalog hashes, engine semantics, reports and the deterministic re-execution check.">
      <Body />
    </ResearchPage>
  );
}
