"use client";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Data } from "plotly.js";
import { toast } from "sonner";
import { AnimatedTabBar } from "@/components/ui/animated-tabs";
import { Modal, ModalBody, ModalContent, ModalFooter, ModalTrigger, useModal } from "@/components/ui/animated-modal";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Plot, useVizTokens } from "@/components/charts/Plot";
import { PageHeader, Section } from "@/components/common/Section";
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
    <Section><InlineProgress stage={d.stage} progress={d.progress} /></Section>;
  const res = d.results;
  const p = res.pairs[pair];
  const div = p.divergent[path];
  const label = (rid: string) => res.policies.find((x: any) => x.run_id === rid)?.label ?? rid;
  return (
    <div className="space-y-4">
      <Section title="Policies on common paths" description={`${res.common.n_paths} paths · ${res.common.generator} · ${res.common.universe} · seed ${res.common.seed}`}>
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
      </Section>
      {res.pairs.length > 1 ? (
        <Field label="Pair"><NativeSelect value={String(pair)} onChange={(v) => { setPair(Number(v)); setPath(0); }}
          options={res.pairs.map((q: any, i: number) => ({ value: String(i), label: "#1 vs #" + (i + 2) }))} /></Field>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Paired path outcomes" description={`Per-path CE; ${pct(p.share_b_better, 0)} of paths favour #${pair + 2}. Points above the diagonal favour #${pair + 2}.`}>
          <Plot height={340} data={[
            { x: p.scatter.a, y: p.scatter.b, type: "scattergl", mode: "markers", name: "paths", marker: { size: 4, color: t.series[0], opacity: 0.45 },
              hovertemplate: "#1 $%{x:,.0f}<br>#" + (pair + 2) + " $%{y:,.0f}<extra></extra>" },
            { x: [Math.min(...p.scatter.a), Math.max(...p.scatter.a)], y: [Math.min(...p.scatter.a), Math.max(...p.scatter.a)], type: "scatter", mode: "lines",
              name: "equal", line: { width: 1, dash: "dot", color: t.text2 }, hoverinfo: "skip" },
          ] as Data[]} layout={{ hovermode: "closest", showlegend: false, xaxis: { title: { text: "#1 path CE ($/yr)" }, tickformat: "$~s" },
            yaxis: { title: { text: `#${pair + 2} path CE ($/yr)` }, tickformat: "$~s" } }} />
          <div className="mt-2 text-xs text-muted-foreground">ΔCE #{pair + 2} vs #1: <b className="text-foreground">{signedPct(p.delta_b_vs_a.delta)}</b> ± {pct(p.delta_b_vs_a.se, 2)}</div>
        </Section>
        <Section title="Divergent-path explorer" description={`#1 fails while #${pair + 2} survives on ${p.n_a_fails_b_survives} paths; the reverse on ${p.n_b_fails_a_survives}.`}>
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
        </Section>
      </div>
      <Provenance meta={d} runId={id} />
    </div>
  );
}

function Validation({ runs }: { runs: RunRow[] }) {
  const [runId, setRunId] = useState<string>("");
  const job = useJob(runId ? "/v1/validation/" + runId : null, { n_param_boot: 20, max_paths: 10000 });
  const t = useVizTokens();
  const d = job.data;
  const v = d?.results;
  return (
    <div className="space-y-4">
      <Field label="Run to validate"><NativeSelect value={runId} onChange={setRunId} options={[{ value: "", label: "Select a run…" },
        ...runs.map((r) => ({ value: r.run_id, label: ((r.summary?.policy as string) ?? r.kind) + " · " + shortId(r.run_id) }))]} /></Field>
      {d && d.status !== "done" ? (d.status === "failed" ? <pre className="text-xs text-destructive">{d.error}</pre> : <Section><InlineProgress stage={d.stage ?? "queued"} progress={d.progress ?? 0} /></Section>) : null}
      {v ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Robust (sign survives MC, parameter and model uncertainty)" value={v.robust ? "Yes" : "No"} />
            <Stat label="Parameter bootstrap: share ΔCE > 0" value={pct(v.parameter_uncertainty.share_positive, 0)} sub={v.parameter_uncertainty.n + " re-estimations"} />
            <Stat label="Cohort replay: policy better" value={pct(v.cohort_replay.share_policy_better, 0)} sub={v.cohort_replay.n_cohorts + " overlapping cohorts"} />
            <Stat label="Cohort ΔCE (paired)" value={signedPct(v.cohort_replay.delta_paired.delta)} sub={"± " + pct(v.cohort_replay.delta_paired.se, 2) + " (not independent)"} />
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Section title="Monte Carlo convergence" description="ΔCE ± 2 SE as paths grow.">
              <Plot height={260} data={[{ x: v.convergence.map((c: any) => c.n_paths), y: v.convergence.map((c: any) => c.delta * 100), type: "scatter", mode: "lines+markers",
                error_y: { type: "data", array: v.convergence.map((c: any) => 2 * c.se * 100), color: t.text2 }, marker: { size: 8, color: t.series[0] }, line: { color: t.series[0], width: 2 }, name: "ΔCE" }]}
                layout={{ xaxis: { type: "log", title: { text: "paths" } }, yaxis: { title: { text: "ΔCE %" } }, showlegend: false }} />
            </Section>
            <Section title="Parameter uncertainty" description="Scenario model re-estimated on bootstrap resamples of history.">
              <Plot height={260} data={[{ x: v.parameter_uncertainty.replications.filter((x: any) => x !== null).map((x: number) => x * 100), type: "histogram",
                marker: { color: t.series[0] }, nbinsx: 20, name: "ΔCE" } as Data]} layout={{ xaxis: { title: { text: "ΔCE %" } }, showlegend: false, hovermode: "closest" }} />
            </Section>
            <Section title="Model uncertainty" description="Same frozen policy under each generator.">
              <Plot height={260} data={[{ type: "bar", x: v.model_uncertainty.map((m: any) => m.generator), y: v.model_uncertainty.map((m: any) => (m.delta ?? 0) * 100),
                error_y: { type: "data", array: v.model_uncertainty.map((m: any) => 2 * (m.se ?? 0) * 100), color: t.text2 },
                marker: { color: v.model_uncertainty.map((m: any) => ((m.delta ?? 0) >= 0 ? t.series[0] : t.series[7])) } } as Data]}
                layout={{ yaxis: { title: { text: "ΔCE %" } }, showlegend: false, hovermode: "closest" }} />
            </Section>
          </div>
          <Section title="Historical cohort replay" description={v.cohort_replay.caveat + ` · ${v.cohort_replay.horizon_years}-year horizon`}>
            <Plot height={280} data={[
              { x: v.cohort_replay.start, y: v.cohort_replay.ce_policy, type: "scatter", mode: "lines", name: "policy", line: { width: 2, color: t.series[0] } },
              { x: v.cohort_replay.start, y: v.cohort_replay.ce_benchmark, type: "scatter", mode: "lines", name: "benchmark", line: { width: 2, dash: "dash", color: t.series[1] } },
            ] as Data[]} layout={{ yaxis: { tickformat: "$~s", title: { text: "cohort CE ($/yr)" } }, xaxis: { title: { text: "cohort start" } } }} />
          </Section>
          <Provenance meta={d} runId={d.run_id} />
        </>
      ) : null}
    </div>
  );
}

function Attribution() {
  const sweeps = useSweeps();
  const done = (sweeps.data?.sweeps ?? []).filter((s) => s.status === "done");
  const [sid, setSid] = useState("");
  const job = useJob(sid ? "/v1/attribution/" + sid : null, { universe: "modern", by_regime: true, n_paths: 1000 });
  const t = useVizTokens();
  const a = job.data?.results;
  return (
    <div className="space-y-4">
      <Field label="Sweep (base investor)"><NativeSelect value={sid} onChange={setSid} options={[{ value: "", label: "Select a sweep…" },
        ...done.map((s) => ({ value: s.run_id, label: (s.label ?? s.run_id).slice(0, 80) }))]} /></Field>
      {job.data && job.data.status !== "done" ? (job.data.status === "failed" ? <pre className="text-xs text-destructive">{job.data.error}</pre> :
        <Section><InlineProgress stage={job.data.stage ?? "queued"} progress={job.data.progress ?? 0} /><div className="mt-2 text-xs text-muted-foreground">Exact Shapley over 2^k sleeve subsets, each a fitted static CRRA mix — a few minutes.</div></Section>) : null}
      {a ? (
        <>
          <Section title="Shapley asset-class utility by regime (headline exhibit 4)" description={`Base universe ${a.base.map(assetLabel).join(" + ")}; ΔCE in $/yr attributed to each added sleeve (${a.window[0]} → ${a.window[1]}).`}>
            <Plot height={340} data={a.conditions.map((c: any, i: number) => ({ type: "bar", name: c.condition, x: a.sleeves.map(assetLabel), y: a.sleeves.map((k: string) => c.shapley[k]),
              marker: { color: t.series[i % 8] }, hovertemplate: "%{x}: $%{y:,.0f}<extra>" + c.condition + "</extra>" })) as Data[]}
              layout={{ barmode: "group", yaxis: { title: { text: "Shapley MU ($/yr)" } }, hovermode: "closest" }} />
          </Section>
          <Section title="Marginal utility of adding one sleeve to the base" description="MU_k = CE*(A ∪ {k}) − CE*(A), with paired SE.">
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
          </Section>
        </>
      ) : null}
    </div>
  );
}

function Hypotheses() {
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
        <div className="grid gap-3 md:grid-cols-2">
          {h.map((x) => (
            <Section key={x.id} title={<span className="flex items-center gap-2">{x.id}
              {x.status === "skipped" ? <Badge variant="outline">skipped</Badge> : x.falsified ? <Badge variant="destructive">falsified</Badge> : <Badge variant="secondary">not falsified</Badge>}</span>}
              description={x.statistic ?? x.reason}>
              <div className="text-xs text-muted-foreground">{x.rule}</div>
              <pre className="mt-2 max-h-56 overflow-auto rounded bg-muted/40 p-2 text-[11px]">{JSON.stringify(x.results ?? x.by_benchmark ?? x.by_sleeve ?? {}, null, 1)}</pre>
            </Section>
          ))}
        </div>
      ) : job.data?.status === "none" ? <div className="text-sm text-muted-foreground">No hypothesis run yet.</div> : null}
    </div>
  );
}

export function Compare() {
  const params = useSearchParams();
  const router = useRouter();
  const [tab, setTab] = useState(params.get("tab") ?? "compare");
  const id = params.get("id");
  const runs = useRuns("experiment", 200);
  const pickable = useMemo(() => (runs.data?.runs ?? []).filter((r) => r.status === "done" && !String(r.summary?.policy ?? "").startsWith("grid DP")), [runs.data]);
  async function onCompare(ids: string[]) {
    try {
      const r = await apiPost<{ status: string }>("/v1/compare", { run_ids: ids });
      router.push("/compare?id=" + r.run_id);
    } catch (e) {
      toast.error(String((e as Error).message));
    }
  }
  return (
    <div>
      <PageHeader eyebrow="05" title="Strategy Comparison & Validation"
        description="Paired ΔCE on common random numbers, the paths where one policy fails and the other survives, and the three separate sources of uncertainty: Monte Carlo, parameter and model.">
        <Modal>
          <ModalTrigger className="rounded-full border border-border bg-background px-5 py-2 text-sm">Pick policies to compare</ModalTrigger>
          <Picker runs={pickable} onCompare={onCompare} />
        </Modal>
      </PageHeader>
      <AnimatedTabBar className="mb-5" value={tab} onChange={setTab} tabs={[{ title: "Comparison", value: "compare" }, { title: "Validation", value: "validation" },
        { title: "Attribution", value: "attribution" }, { title: "Hypotheses", value: "hypotheses" }]} />
      {tab === "compare" ? (id ? <Comparison id={id} /> : <Section><div className="py-16 text-center text-sm text-muted-foreground">Pick two to four finished experiments to compare them on common paths.</div></Section>) : null}
      {tab === "validation" ? <Validation runs={pickable} /> : null}
      {tab === "attribution" ? <Attribution /> : null}
      {tab === "hypotheses" ? <Hypotheses /> : null}
    </div>
  );
}
