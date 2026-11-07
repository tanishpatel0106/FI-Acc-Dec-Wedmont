"use client";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Data } from "plotly.js";
import { toast } from "sonner";
import { Modal, ModalBody, ModalContent, ModalFooter, ModalTrigger, useModal } from "@/components/ui/animated-modal";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Plot, useVizTokens } from "@/components/visualizations/Plot";
import { Section as Card } from "@/components/common/Section";
import { Viz } from "@/components/visualizations/VisualizationFrame";
import { Field, NativeSelect } from "@/components/common/Fields";
import { Stat } from "@/components/common/Stat";
import { InlineProgress } from "@/components/experiment/RunProgress";
import { Provenance } from "@/components/experiment/Provenance";
import { apiPost } from "@/lib/api/client";
import { useJob, useRuns, useSweeps } from "@/lib/api/hooks";
import type { RunRow } from "@/lib/api/types";
import { assetLabel, num, pct, shortId, signedPct, usd } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
function Picker({ runs, onCompare }: { runs: RunRow[]; onCompare: (ids: string[]) => void }) {
  const [picked, setPicked] = useState<string[]>([]);
  const { setOpen } = useModal();
  return (
    <ModalBody className="md:max-w-2xl">
      <ModalContent className="max-h-[70vh] overflow-y-auto">
        <h4 className="mb-1 text-lg font-semibold">Pick two to four policies</h4>
        <p className="mb-4 text-xs text-muted-foreground">All are re-evaluated on the first run&apos;s scenario paths (common random numbers).</p>
        <div className="space-y-1">
          {runs.map((r) => {
            const on = picked.includes(r.run_id);
            return (
              <button key={r.run_id} onClick={() => setPicked(on ? picked.filter((p) => p !== r.run_id) : picked.length < 4 ? [...picked, r.run_id] : picked)}
                className={"flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm " + (on ? "border-[var(--viz-s1)] bg-muted/60" : "border-border hover:bg-muted/40")}>
                <span className="truncate">{(r.summary?.policy as string) ?? r.label ?? r.kind}</span>
                <span className="ml-3 shrink-0 font-mono text-xs text-muted-foreground">
                  {on ? "#" + (picked.indexOf(r.run_id) + 1) + " · " : ""}{shortId(r.run_id)} · {usd(r.summary?.ce as number)}
                </span>
              </button>
            );
          })}
          {runs.length === 0 ? <div className="text-sm text-muted-foreground">No finished experiments yet — run some in the Simulator or Optimizer.</div> : null}
        </div>
      </ModalContent>
      <ModalFooter className="gap-3 bg-muted/40">
        <button className="rounded-md border border-border px-3 py-1 text-sm" onClick={() => setPicked([])}>Clear</button>
        <button disabled={picked.length < 2} className="rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground disabled:opacity-40"
          onClick={() => { onCompare(picked); setOpen(false); }}>Compare on common paths</button>
      </ModalFooter>
    </ModalBody>
  );
}

function Comparison({ id }: { id: string }) {
  const job = useJob("/v1/compare/" + id);
  const t = useVizTokens();
  const [pair, setPair] = useState(0);
  const [path, setPath] = useState(0);
  const d = job.data;
  if (!d) return <div className="h-80 animate-pulse rounded-xl bg-muted/40" />;
  if (d.status !== "done") return d.status === "failed" ? <pre className="text-xs text-destructive">{d.error}</pre> :
    <InlineProgress stage={d.stage} progress={d.progress} />;
  const res = d.results;
  const p = res.pairs[pair];
  const div = p.divergent[path];
  const label = (rid: string) => res.policies.find((x: any) => x.run_id === rid)?.label ?? rid;
  return (
    <div className="space-y-4">
      <Viz id="CO-11" runId={id} cls="model_generated" footnote={`${res.common.n_paths} paths · ${res.common.generator} · ${res.common.universe} · seed ${res.common.seed}`}>
        <Table>
          <TableHeader><TableRow><TableHead>Policy</TableHead><TableHead className="text-right">CE</TableHead><TableHead className="text-right">ΔCE vs #1 (paired)</TableHead>
            <TableHead className="text-right">P(depletion)</TableHead><TableHead className="text-right">CVaR95 shortfall</TableHead><TableHead>Run</TableHead></TableRow></TableHeader>
          <TableBody>
            {res.policies.map((x: any, i: number) => (
              <TableRow key={x.run_id}><TableCell>#{i + 1} {x.label}</TableCell><TableCell className="text-right tabular-nums">{usd(x.ce.ce)} ± {usd(x.ce.se)}</TableCell>
                <TableCell className="text-right tabular-nums">{x.delta_vs_first ? <>{signedPct(x.delta_vs_first.delta)} ± {pct(x.delta_vs_first.se, 2)}</> : "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{pct(x.shortfall.p_depletion)}</TableCell><TableCell className="text-right tabular-nums">{num(x.shortfall.cvar95_L)}</TableCell>
                <TableCell className="font-mono text-xs">{shortId(x.run_id)}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
      </Viz>
      {res.pairs.length > 1 ? (
        <Field label="Pair"><NativeSelect value={String(pair)} onChange={(v) => { setPair(Number(v)); setPath(0); }}
          options={res.pairs.map((q: any, i: number) => ({ value: String(i), label: "#1 vs #" + (i + 2) }))} /></Field>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Viz id="CO-12" runId={id} cls="model_generated" question={`Per-path CE; ${pct(p.share_b_better, 0)} of paths favour #${pair + 2}. Points above the diagonal favour #${pair + 2}.`} selection={{ pair: "#1 vs #" + (pair + 2) }}>
          <Plot height={340} data={[
            { x: p.scatter.a, y: p.scatter.b, type: "scattergl", mode: "markers", name: "paths", marker: { size: 4, color: t.series[0], opacity: 0.45 },
              hovertemplate: "#1 $%{x:,.0f}<br>#" + (pair + 2) + " $%{y:,.0f}<extra></extra>" },
            { x: [Math.min(...p.scatter.a), Math.max(...p.scatter.a)], y: [Math.min(...p.scatter.a), Math.max(...p.scatter.a)], type: "scatter", mode: "lines",
              name: "equal", line: { width: 1, dash: "dot", color: t.text2 }, hoverinfo: "skip" },
          ] as Data[]} layout={{ hovermode: "closest", showlegend: false, xaxis: { title: { text: "#1 path CE ($/yr)" }, tickformat: "$~s" },
            yaxis: { title: { text: `#${pair + 2} path CE ($/yr)` }, tickformat: "$~s" } }} />
          <div className="mt-2 text-xs text-muted-foreground">ΔCE #{pair + 2} vs #1: <b className="text-foreground">{signedPct(p.delta_b_vs_a.delta)}</b> ± {pct(p.delta_b_vs_a.se, 2)}</div>
        </Viz>
        <Viz id="CO-13" runId={id} cls="model_generated" question={`#1 fails while #${pair + 2} survives on ${p.n_a_fails_b_survives} paths; the reverse on ${p.n_b_fails_a_survives}.`} selection={{ pair: "#1 vs #" + (pair + 2), path: div?.path }}>
          {p.divergent.length === 0 ? <div className="py-16 text-center text-sm text-muted-foreground">No divergent paths.</div> : (
            <>
              <Field label="Path"><NativeSelect value={String(path)} onChange={(v) => setPath(Number(v))} options={p.divergent.map((x: any, i: number) => ({
                value: String(i), label: `path ${x.path}: ${x.a_depleted ? "#1 depletes at " + num(x.a_depletion_age, 1) : "#" + (pair + 2) + " depletes at " + num(x.b_depletion_age, 1)} · equity 10y ${pct(x.cum_real_equity_first_10y, 0)}` }))} /></Field>
              <Plot height={280} data={[
                { x: res.ages, y: div.a_wealth, type: "scatter", mode: "lines", name: "#1 " + label(p.a).slice(0, 30), line: { width: 2, color: t.series[0] } },
                { x: res.ages, y: div.b_wealth, type: "scatter", mode: "lines", name: `#${pair + 2} ` + label(p.b).slice(0, 30), line: { width: 2, color: t.series[1] } },
              ] as Data[]} layout={{ yaxis: { tickformat: "$~s", title: { text: "real wealth" } }, xaxis: { title: { text: "Age" } } }} />
            </>
          )}
        </Viz>
      </div>
      <Provenance meta={d} runId={id} />
    </div>
  );
}

/** Run validation: convergence, parameter, model, sequence, window, tail and cohort checks for one saved run. */
export function RunValidation({ runs }: { runs: RunRow[] }) {
  const [runId, setRunId] = useState<string>("");
  const [launch, setLaunch] = useState<string | null>(null);
  const job = useJob(runId ? "/v1/validation/" + runId : null, { n_param_boot: 20, max_paths: 10000, submit: launch === runId });
  const t = useVizTokens();
  const d = job.data;
  const v = d?.results;
  return (
    <div className="space-y-4">
      <Field label="Run to validate"><NativeSelect value={runId} onChange={setRunId} options={[{ value: "", label: "Select a run…" },
        ...runs.map((r) => ({ value: r.run_id, label: ((r.summary?.policy as string) ?? r.kind) + " · " + shortId(r.run_id) }))]} /></Field>
      {d && d.status === "none" ? (
        <button onClick={() => setLaunch(runId)} className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">
          Run validation (convergence, 20 parameter re-estimations, 3 generators, cohort replay)
        </button>
      ) : null}
      {d && d.status !== "done" && d.status !== "none" ? (d.status === "failed" ? <pre className="text-xs text-destructive">{d.error}</pre> : <InlineProgress stage={d.stage ?? "queued"} progress={d.progress ?? 0} />) : null}
      {v ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Robust (sign survives MC, parameter and model uncertainty)" value={v.robust ? "Yes" : "No"} />
            <Stat label="Parameter bootstrap: share ΔCE > 0" value={pct(v.parameter_uncertainty.share_positive, 0)} sub={v.parameter_uncertainty.n + " re-estimations"} />
            <Stat label="Cohort replay: policy better" value={pct(v.cohort_replay.share_policy_better, 0)} sub={v.cohort_replay.n_cohorts + " overlapping cohorts"} />
            <Stat label="Cohort ΔCE (paired)" value={signedPct(v.cohort_replay.delta_paired.delta)} sub={"± " + pct(v.cohort_replay.delta_paired.se, 2) + " (not independent)"} />
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Viz id="RS-12" runId={d.run_id} cls="model_generated">
              <Plot height={260} data={[{ x: v.convergence.map((c: any) => c.n_paths), y: v.convergence.map((c: any) => c.delta * 100), type: "scatter", mode: "lines+markers",
                error_y: { type: "data", array: v.convergence.map((c: any) => 2 * c.se * 100), color: t.text2 }, marker: { size: 8, color: t.series[0] }, line: { color: t.series[0], width: 2 }, name: "ΔCE" }]}
                layout={{ xaxis: { type: "log", title: { text: "paths" } }, yaxis: { title: { text: "ΔCE %" } }, showlegend: false }} />
            </Viz>
            <Viz id="RS-13" runId={d.run_id} cls="model_generated">
              <Plot height={260} data={[{ x: v.parameter_uncertainty.replications.filter((x: any) => x !== null).map((x: number) => x * 100), type: "histogram",
                marker: { color: t.series[0] }, nbinsx: 20, name: "ΔCE" } as Data]} layout={{ xaxis: { title: { text: "ΔCE %" } }, showlegend: false, hovermode: "closest" }} />
            </Viz>
            <Viz id="RS-14" runId={d.run_id} cls="model_generated">
              <Plot height={260} data={[{ type: "bar", x: v.model_uncertainty.map((m: any) => m.generator), y: v.model_uncertainty.map((m: any) => (m.delta ?? 0) * 100),
                error_y: { type: "data", array: v.model_uncertainty.map((m: any) => 2 * (m.se ?? 0) * 100), color: t.text2 },
                marker: { color: v.model_uncertainty.map((m: any) => ((m.delta ?? 0) >= 0 ? t.series[0] : t.series[7])) } } as Data]}
                layout={{ yaxis: { title: { text: "ΔCE %" } }, showlegend: false, hovermode: "closest" }} />
            </Viz>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {v.sequence_risk ? (
              <Viz id="RS-15" runId={d.run_id} cls="model_generated" question={`Months of the worst benchmark cohort (${v.sequence_risk.cohort_start}) permuted ${v.sequence_risk.n_permutations}×, values fixed. ${v.sequence_risk.note}.`}>
                <Plot height={240} data={[
                  { x: v.sequence_risk.permuted_benchmark, type: "histogram", name: "benchmark (permuted)", marker: { color: t.series[1] }, opacity: 0.7 },
                  { x: v.sequence_risk.permuted_policy, type: "histogram", name: "policy (permuted)", marker: { color: t.series[0] }, opacity: 0.7 },
                ] as Data[]} layout={{ barmode: "overlay", hovermode: "closest", xaxis: { tickformat: "$~s", title: { text: "CE ($/yr)" } },
                  shapes: [{ type: "line", x0: v.sequence_risk.benchmark.actual, x1: v.sequence_risk.benchmark.actual, yref: "paper", y0: 0, y1: 1, line: { color: t.series[1], width: 2, dash: "dot" } },
                    { type: "line", x0: v.sequence_risk.policy.actual, x1: v.sequence_risk.policy.actual, yref: "paper", y0: 0, y1: 1, line: { color: t.series[0], width: 2, dash: "dot" } }] }} />
                <div className="mt-1 text-xs text-muted-foreground">Timing effect (actual − permuted mean): policy {usd(v.sequence_risk.policy.timing_effect)}, benchmark {usd(v.sequence_risk.benchmark.timing_effect)}. Dotted = actual order.</div>
              </Viz>
            ) : null}
            {v.calibration_windows ? (
              <Viz id="RS-16" runId={d.run_id} cls="model_generated">
                <Plot height={240} data={[{ type: "bar", x: v.calibration_windows.map((w: any) => w.window), y: v.calibration_windows.map((w: any) => (w.delta ?? 0) * 100),
                  error_y: { type: "data", array: v.calibration_windows.map((w: any) => 2 * (w.se ?? 0) * 100), color: t.text2 },
                  marker: { color: v.calibration_windows.map((w: any) => ((w.delta ?? 0) >= 0 ? t.series[0] : t.series[7])) } } as Data]}
                  layout={{ yaxis: { title: { text: "ΔCE %" } }, showlegend: false, hovermode: "closest" }} />
              </Viz>
            ) : null}
            {v.tail_coverage ? (
              <Viz id="RS-17" runId={d.run_id} cls="model_generated">
                <Table>
                  <TableHeader><TableRow><TableHead>Horizon</TableHead><TableHead className="text-right">Realised</TableHead><TableHead className="text-right">Simulated</TableHead></TableRow></TableHeader>
                  <TableBody>{v.tail_coverage.map((r: any) => (
                    <TableRow key={r.horizon_months}><TableCell>{r.horizon_months}m</TableCell><TableCell className="text-right tabular-nums">{pct(r.realised, 2)}</TableCell><TableCell className="text-right tabular-nums">{pct(r.simulated, 2)}</TableCell></TableRow>
                  ))}</TableBody>
                </Table>
              </Viz>
            ) : null}
          </div>
          <Viz id="RS-18" runId={d.run_id} cls="observed" footnote={v.cohort_replay.caveat + ` · ${v.cohort_replay.horizon_years}-year horizon`}>
            <Plot height={280} data={[
              { x: v.cohort_replay.start, y: v.cohort_replay.ce_policy, type: "scatter", mode: "lines", name: "policy", line: { width: 2, color: t.series[0] } },
              { x: v.cohort_replay.start, y: v.cohort_replay.ce_benchmark, type: "scatter", mode: "lines", name: "benchmark", line: { width: 2, dash: "dash", color: t.series[1] } },
            ] as Data[]} layout={{ yaxis: { tickformat: "$~s", title: { text: "cohort CE ($/yr)" } }, xaxis: { title: { text: "cohort start" } } }} />
          </Viz>
          <Provenance meta={d} runId={d.run_id} />
        </>
      ) : null}
    </div>
  );
}

/** Exact Shapley attribution of utility to asset sleeves for a sweep base investor (unconditional and by regime). */
export function SweepAttribution() {
  const sweeps = useSweeps();
  const done = (sweeps.data?.sweeps ?? []).filter((s) => s.status === "done");
  const [sid, setSid] = useState("");
  const [launch, setLaunch] = useState<string | null>(null);
  const job = useJob(sid ? "/v1/attribution/" + sid : null, { universe: "modern", by_regime: true, n_paths: 1000, submit: launch === sid });
  const t = useVizTokens();
  const a = job.data?.results;
  return (
    <div className="space-y-4">
      <Field label="Sweep (base investor)"><NativeSelect value={sid} onChange={setSid} options={[{ value: "", label: "Select a sweep…" },
        ...done.map((s) => ({ value: s.run_id, label: (s.label ?? s.run_id).slice(0, 80) }))]} /></Field>
      {job.data && job.data.status === "none" ? (
        <button onClick={() => setLaunch(sid)} className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">
          Compute attribution (modern universe, unconditional + by regime)
        </button>
      ) : null}
      {job.data && job.data.status !== "done" && job.data.status !== "none" ? (job.data.status === "failed" ? <pre className="text-xs text-destructive">{job.data.error}</pre> :
        <div><InlineProgress stage={job.data.stage ?? "queued"} progress={job.data.progress ?? 0} /><div className="mt-2 text-xs text-muted-foreground">Exact Shapley over 2^k sleeve subsets, each a fitted static CRRA mix — a few minutes.</div></div>) : null}
      {a ? (
        <>
          <Viz id="OP-11" runId={job.data?.run_id} cls="model_generated" question={`Base universe ${a.base.map(assetLabel).join(" + ")}; ΔCE in $/yr attributed to each added sleeve (${a.window[0]} → ${a.window[1]}).`}>
            <Plot height={340} data={a.conditions.map((c: any, i: number) => ({ type: "bar", name: c.condition, x: a.sleeves.map(assetLabel), y: a.sleeves.map((k: string) => c.shapley[k]),
              marker: { color: t.series[i % 8] }, hovertemplate: "%{x}: $%{y:,.0f}<extra>" + c.condition + "</extra>" })) as Data[]}
              layout={{ barmode: "group", yaxis: { title: { text: "Shapley MU ($/yr)" } }, hovermode: "closest" }} />
          </Viz>
          <Viz id="OP-12" runId={job.data?.run_id} cls="model_generated">
            <Table>
              <TableHeader><TableRow><TableHead>Condition</TableHead>{a.sleeves.map((k: string) => <TableHead key={k} className="text-right">{assetLabel(k)}</TableHead>)}<TableHead className="text-right">CE base → full</TableHead></TableRow></TableHeader>
              <TableBody>
                {a.conditions.map((c: any) => (
                  <TableRow key={c.condition}><TableCell>{c.condition}</TableCell>
                    {a.sleeves.map((k: string) => <TableCell key={k} className="text-right tabular-nums">{signedPct(c.marginal[k].mu_pct)} <span className="text-muted-foreground">± {pct(c.marginal[k].se_pct, 2)}</span></TableCell>)}
                    <TableCell className="text-right tabular-nums">{usd(c.ce_base)} → {usd(c.ce_full)}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </Viz>
        </>
      ) : null}
    </div>
  );
}

/** Original H1–H4 hypothesis tests on the sweep / attribution / DP runs. */
export function HypothesisTests() {
  const job = useJob("/v1/research/hypotheses");
  const sweeps = useSweeps();
  const runs = useRuns("attribution", 20);
  async function run() {
    const head = (sweeps.data?.sweeps ?? []).find((s) => s.status === "done" && (s.summary as any)?.kind === "decumulation");
    const att = (runs.data?.runs ?? []).find((r) => r.status === "done");
    try {
      await apiPost("/v1/research/hypotheses", { sweep_id: head?.run_id ?? null, attribution_id: att?.run_id ?? null, n_boot: 5 });
      toast.success("Hypothesis tests submitted");
      job.refetch();
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }
  const h = job.data?.results?.hypotheses as any[] | undefined;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={run} className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">Run H1–H4 tests</button>
        <span className="text-xs text-muted-foreground">Uses the latest decumulation sweep (H2) and attribution run (H3, H4); H1 re-solves the DP under a parameter bootstrap.</span>
      </div>
      {job.data?.status && job.data.status !== "done" && job.data.status !== "none" ? <InlineProgress stage={job.data.status} progress={job.data.progress ?? 0} /> : null}
      {h ? (
        <Viz id="RS-11" runId={job.data?.run_id} cls="model_generated">
        <div className="grid gap-3 md:grid-cols-2">
          {h.map((x) => (
            <Card key={x.id} title={<span className="flex items-center gap-2">{x.id}
              {x.status === "skipped" ? <Badge variant="outline">skipped</Badge> : x.falsified ? <Badge variant="destructive">falsified</Badge> : <Badge variant="secondary">not falsified</Badge>}</span>}
              description={x.statistic ?? x.reason}>
              <div className="text-xs text-muted-foreground">{x.rule}</div>
              <pre className="mt-2 max-h-56 overflow-auto rounded bg-muted/40 p-2 text-[11px]">{JSON.stringify(x.results ?? x.by_benchmark ?? x.by_sleeve ?? {}, null, 1)}</pre>
            </Card>
          ))}
        </div>
        </Viz>
      ) : job.data?.status === "none" ? <Viz id="RS-11" empty="Not computed: no H1–H4 hypothesis run exists yet.">{null}</Viz> : null}
    </div>
  );
}

/** Hook returning finished experiment runs that can be compared on common paths. */
export function usePickableRuns() {
  const runs = useRuns("experiment", 200);
  return useMemo(() => (runs.data?.runs ?? []).filter((r) => r.status === "done" && !String(r.summary?.policy ?? "").startsWith("grid DP")), [runs.data]);
}

/** Saved-run comparison: pick 2–4 finished experiments; all are re-evaluated on the first run's paths. */
export function SavedRunComparison() {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("id");
  const pickable = usePickableRuns();
  async function onCompare(ids: string[]) {
    try {
      const r = await apiPost<{ status: string }>("/v1/compare", { run_ids: ids });
      router.push("/compare?section=saved-runs&id=" + r.run_id);
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-3xl text-xs text-muted-foreground">Paired ΔCE on common random numbers and the paths where one policy fails and the other survives. Saved runs come from the
          Interactive Lifecycle Simulator, the policy family and the CE sweeps (target-weight kernel; compatibility is checked by the backend).</p>
        <Modal>
          <ModalTrigger className="rounded-full border border-border bg-background px-5 py-2 text-sm">Pick saved runs to compare</ModalTrigger>
          <Picker runs={pickable} onCompare={onCompare} />
        </Modal>
      </div>
      {id ? <Comparison id={id} /> : <Viz id="CO-11" empty="Not computed: pick two to four finished experiments to compare them on common paths.">{null}</Viz>}
    </div>
  );
}
