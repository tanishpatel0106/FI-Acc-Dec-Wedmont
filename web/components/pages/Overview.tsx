"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { BentoGrid, BentoGridItem } from "@/components/ui/bento-grid";
import { GlowingEffect } from "@/components/ui/glowing-effect";
import { Timeline } from "@/components/ui/timeline";
import { SweepHeadlines } from "@/components/research/overview/SweepHeadlines";
import { ApplicationGuide, Hero, JourneyCards, QuestionNavigator, StudyStatus, WorkflowDiagram } from "@/components/research/overview/Guide";
import { DataTable, Empty, GradeTag, Kpi, Viz } from "@/components/research/kit";
import { Heat, pct } from "@/components/visualizations/charts";
import { Plot, useVizTokens } from "@/components/visualizations/Plot";
import { API_BASE } from "@/lib/api/client";
import { useV2 } from "@/lib/api/v2";
import type { Data } from "plotly.js";

/* eslint-disable @typescript-eslint/no-explicit-any */
function Tile({ tile, active, onClick }: { tile: any; active: boolean; onClick: () => void }) {
  const v = tile.value;
  const isPct = tile.id === "bond_threshold" || tile.id === "ce_improvement";
  const shown = v === null || v === undefined ? (tile.status === "no_feasible_allocation" ? "No feasible allocation" : "Not established")
    : tile.id === "bond_threshold" || tile.id === "ce_improvement" ? pct(v, 0) : (v > 0 ? "+" : "") + (v * 100).toFixed(2) + "%";
  return (
    <button onClick={onClick} className="relative block h-full rounded-xl text-left">
      {active ? <GlowingEffect spread={30} glow proximity={48} inactiveZone={0.02} borderWidth={2} disabled={false} /> : null}
      <div className="h-full rounded-xl border border-border bg-card p-4">
        <div className="text-xs text-muted-foreground">{tile.title}</div>
        <div className="mt-1 text-2xl font-semibold tabular-nums">{shown}</div>
        {tile.label ? <div className="text-xs">{tile.label}</div> : null}
        <div className="mt-1 text-[11px] text-muted-foreground">{tile.ci && tile.ci[0] !== null && tile.ci[0] !== undefined ? (isPct ? "range " + pct(tile.ci[0], 0) + "–" + pct(tile.ci[1], 0) : "95% CI " + (tile.ci[0] * 100).toFixed(2) + "% to " + (tile.ci[1] * 100).toFixed(2) + "%") : "uncertainty: not identified"}</div>
        <div className="mt-1 text-[11px] text-muted-foreground">vs {tile.benchmark ?? "benchmark"} · {tile.universe} · {(tile.date ?? "").slice(0, 10)} · run {String(tile.run_id).slice(0, 8)}</div>
        <div className="mt-1"><GradeTag grade="conditional" /></div>
      </div>
    </button>
  );
}

function Continuum({ c }: { c: any }) {
  const t = useVizTokens();
  const router = useRouter();
  const ai = c.ages.indexOf(65) >= 0 ? c.ages.indexOf(65) : Math.floor(c.ages.length / 2);
  const data: Data[] = [{ type: "scatter", mode: "markers", x: c.q, y: c.q.map(() => 0), marker: { size: 22, symbol: "square", color: c.b_ce[ai], cmin: 0, cmax: 1,
    colorscale: [[0, t.divMid], [1, t.series[2]]], colorbar: { title: { text: "bond share" }, thickness: 8, tickformat: ".0%" } },
    customdata: c.b_ce[ai] as any, hovertemplate: "q %{x:+.1%}<br>%{customdata:.0%} bonds (CE-optimal, age " + c.ages[ai] + ")<br>q<0: household contributes · q>0: household withdraws<extra></extra>" } as Data];
  return <Plot height={130} data={data} onClick={() => router.push("/lifecycle-flows?section=overview")} layout={{ hovermode: "closest", margin: { l: 16, r: 16, t: 8, b: 36 },
    yaxis: { visible: false, range: [-1, 1] }, xaxis: { title: { text: "signed net draw q  (← contributions · 0 · withdrawals →)" }, tickformat: "+.0%", zeroline: true },
    shapes: [{ type: "line", x0: 0, x1: 0, y0: -1, y1: 1, line: { width: 2, color: t.text } }] as any }} />;
}

function Launcher() {
  const figs = useV2("/v1/results/figures", undefined, { refetch: 15_000 });
  const [sel, setSel] = useState("F1");
  const f = figs.data?.figures.find((x: any) => x.figure === sel);
  const spec = useV2(f?.run_id ? "/v1/runs/" + f.run_id + "/inspect" : null);
  return (
    <div className="space-y-2 text-xs">
      <select value={sel} onChange={(e) => setSel(e.target.value)} className="h-8 rounded border border-input bg-transparent px-2">
        {(figs.data?.figures ?? []).map((x: any) => <option key={x.figure} value={x.figure}>{x.figure} · {x.title}</option>)}</select>
      {f ? <>
        <div className="flex items-center gap-2"><GradeTag grade={f.evidence_grade} /> status {f.status} {f.run_id ? "· run " + f.run_id.slice(0, 10) : ""} · <Link className="underline" href={f.page}>open page</Link></div>
        <code className="block rounded border border-border p-2">{f.reproduce}</code>
        <button className="rounded border border-border px-2 py-1 hover:bg-muted" onClick={() => { void navigator.clipboard?.writeText(JSON.stringify(spec.data?.spec ?? {}, null, 2)); toast.success("Spec copied"); }}>Copy spec JSON</button>
        {f.run_id ? <a className="ml-2 underline" href={API_BASE + "/v1/studies/run/" + f.run_id + "/export?format=json"}>derived data</a> : null}
      </> : null}
    </div>
  );
}

function Body() {
  const ov = useV2("/v1/overview/v2", undefined, { refetch: 20_000 });
  const [active, setActive] = useState<string | null>(null);
  const d = ov.data;
  if (ov.isError) return <Empty>API unreachable ({String((ov.error as Error).message)}). Start it with <code>make api</code>.</Empty>;
  if (!d) return <div className="h-96 animate-pulse rounded-xl bg-muted/40" />;
  const fm = d.frontier_mini;
  const opt = fm?.optima?.find((o: any) => Math.abs(o.r - 0.05) < 1e-9) ?? fm?.optima?.[Math.floor((fm?.optima?.length ?? 1) / 2)];
  const today = new Date();
  return (
    <div className="space-y-6">
      <p className="text-xs text-muted-foreground">Data as of {d.as_of} (last observation) · {d.wrds ? "WRDS + public" : "public data only (WRDS not ingested)"} · {d.synthetic ? "SYNTHETIC FIXTURE MODE — illustrative only" : "every figure links to a persisted run"}. Research output — not investment advice.</p>
      <Viz id="OV-01" title="Headline research verdict tiles" question="Measured results with uncertainty, benchmark, universe, date and validation state; missing results read 'Not established'." cls="model_generated">
        {d.tiles.length ? <BentoGrid className="mx-0 max-w-none md:auto-rows-auto md:grid-cols-4">{d.tiles.map((t: any) => (
          <div key={t.id}><Tile tile={t} active={active === t.id} onClick={() => setActive(t.id)} /></div>))}
          {d.tiles.length < 4 ? <BentoGridItem className="border-border bg-card" title="Not established" description="Remaining headline results need their studies (see Study computation status)." header={null} icon={null} /> : null}
        </BentoGrid> : <Empty>Not computed: no completed study runs yet. Run <code>python -m lifecycle.cli seed-v2</code> or open a study page and click Run.</Empty>}
      </Viz>
      <div className="grid gap-4 lg:grid-cols-2">
        <Viz id="OV-02" title="Lifecycle continuum strip" question="Signed q from net contributions (left) through zero to net withdrawals (right), coloured by the CE-optimal bond share at 65. Click to open the cohort scenario."
          cls="model_generated" runId={d.continuum?.run_id} empty={d.continuum ? null : "Signed-flow study not computed."}
          definition="q = planned annual net portfolio draw / reference wealth. Household cash flow: labour income + pension − desired consumption.">
          {d.continuum ? <Continuum c={d.continuum} /> : null}
        </Viz>
        <Viz id="OV-03" title="Core bond-necessity mini-contour" question={"Withdrawal rate × bond share; the " + pct(fm?.target ?? 0.9, 0) + " survival contour; × = generators disagree."} cls="model_generated" runId={fm?.run_id}
          empty={fm ? null : "Bond-frontier study not computed."}>
          {fm ? <Link href="/withdrawal-lab?section=overview"><Heat height={260} x={fm.r.filter((_: number, i: number) => i % 2 === 0)} y={fm.b.filter((_: number, i: number) => i % 2 === 0)}
            z={fm.p.filter((_: any, i: number) => i % 2 === 0).map((row: number[]) => row.filter((_, j) => j % 2 === 0))} xTitle="withdrawal" yTitle="bond share" zTitle="P(success)"
            xfmt={(v) => pct(v, 1)} yfmt={(v) => pct(v, 0)} zmin={0} zmax={1} text={false} contours={[{ level: fm.target, label: pct(fm.target, 0) }]} /></Link> : null}
        </Viz>
        <Viz id="OV-04" title="Multi-objective KPI pair" question={"CE-optimal vs survival-optimal bond share at " + pct(opt?.r ?? 0.05, 1) + " withdrawal, with the trade-off."} cls="model_generated" runId={fm?.run_id} empty={opt ? null : "Not established."}>
          {opt ? <div className="grid grid-cols-2 gap-3">
            <Kpi label="CE-optimal bond share" value={pct(opt.b_ce, 0)} sub={"CE $" + Math.round(opt.ce_at_ce_opt).toLocaleString() + " · P(success) " + pct(opt.p_at_ce_opt)} />
            <Kpi label="Survival-optimal bond share" value={pct(opt.b_survival, 0)} sub={"CE $" + Math.round(opt.ce_at_surv_opt).toLocaleString() + " · P(success) " + pct(opt.p_at_surv_opt)} />
            <div className="col-span-2 text-xs text-muted-foreground">Choosing survival over CE costs {((1 - opt.ce_at_surv_opt / opt.ce_at_ce_opt) * 100).toFixed(2)}% of CE and buys {((opt.p_at_surv_opt - opt.p_at_ce_opt) * 100).toFixed(1)}pp of success.</div>
          </div> : null}
        </Viz>
        <Viz id="OV-05" title="Evidence-grade matrix" question="H1–H12 × robustness dimension: supported, contradicted, fragile, not computed. Click through to the research register." cls="model_generated"
          empty={d.evidence ? null : "Evidence study not computed."}>
          {d.evidence ? <Link href="/research?section=hypotheses"><Heat height={300} x={["monte_carlo", "parameter", "model", "historical", "oos", "source_quality"]} y={d.evidence.map((e: any) => e.id)}
            z={d.evidence.map((e: any) => ["monte_carlo", "parameter", "model", "historical", "oos", "source_quality"].map((k) => (e[k] === "pass" ? 1 : e[k] === "fail" ? 0 : e[k] === "not_computed" ? null : 0.5)))}
            mask={d.evidence.map((e: any) => ["monte_carlo", "parameter", "model", "historical", "oos", "source_quality"].map((k) => e[k] === "not_computed"))}
            xTitle="dimension" yTitle="" zTitle="status" zfmt=".1f" zmin={0} zmax={1} text={false} /></Link> : null}
        </Viz>
      </div>
      <SweepHeadlines />
      <Viz id="OV-06" title="Research pipeline timeline" question="Latest data vintage, tests, simulations, calibration, validation — actual timestamps from the registry." cls="observed">
        <Timeline data={d.timeline.map((x: any) => ({ title: (x.at ?? "not run").replace("T", " ").slice(0, 16), content: (
          <div className="text-sm"><div className="font-medium">{x.stage}</div><div className="text-xs text-muted-foreground">{x.detail}{x.run_id ? " · run " + x.run_id.slice(0, 10) : ""}</div></div>) }))} />
      </Viz>
      <h2 id="health" className="pt-4 text-lg font-semibold tracking-tight">Data &amp; research health</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <Viz id="OV-07" title="Data source coverage grid" question="Availability by series: first/last observation, provenance, licence restriction and staleness vs today." cls="observed">
          <div className="max-h-80 overflow-auto"><DataTable rows={d.coverage.map((c: any) => ({ ...c, stale: Math.round((today.getTime() - new Date(c.last_obs).getTime()) / 86400000) }))} columns={[
            { key: "series_id", label: "series" }, { key: "first_obs", label: "first" }, { key: "last_obs", label: "last" }, { key: "stale", label: "days old", fmt: (v) => (v > 75 ? "▲ " + v : String(v)) },
            { key: "provenance", label: "provenance" }, { key: "licence_class", label: "restriction" }, { key: "source", label: "source" }]} /></div>
        </Viz>
        <Viz id="OV-08" title="Reproduce this figure" question="Pick a flagship figure: its run, one-line reproduction command, spec and job status." cls="observed"><Launcher /></Viz>
      </div>
      <StudyStatus />
    </div>
  );
}

/** Research Home: what LIFECYCLE is, what it has established, and where to go next. */
export function Overview() {
  return (
    <div className="space-y-10" data-page="overview">
      <Hero />
      <section aria-labelledby="status-h" className="space-y-4">
        <h2 id="status-h" className="text-lg font-semibold tracking-tight">Research status &amp; key findings</h2>
        <Body />
      </section>
      <ApplicationGuide />
      <QuestionNavigator />
      <WorkflowDiagram />
      <JourneyCards />
    </div>
  );
}
