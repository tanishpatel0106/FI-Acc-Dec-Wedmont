"use client";
import type { Data } from "plotly.js";
import { FanChart } from "@/components/visualizations/FanChart";
import { WeightPath } from "@/components/visualizations/WeightPath";
import { Plot, useVizTokens } from "@/components/visualizations/Plot";
import { Viz } from "@/components/visualizations/VisualizationFrame";
import { Stat } from "@/components/common/Stat";
import { MetricLabel } from "@/components/common/MetricLabel";
import { Badge } from "@/components/ui/badge";
import type { ExperimentResults } from "@/lib/api/types";
import { num, pct, signedPct, usd } from "@/lib/format";
import { Provenance } from "./Provenance";
import { SamplePaths } from "@/components/visualizations/SamplePaths";

export function HeadlineStats({ r }: { r: ExperimentResults }) {
  const d = r.ce.delta;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label={<MetricLabel id="CE">CE consumption (policy)</MetricLabel>} value={usd(r.ce.policy.ce)} sub={"± " + usd(r.ce.policy.se) + " MC SE · real $/yr"} />
      <Stat label={"Benchmark: " + (r.benchmark?.label ?? r.benchmark?.name ?? "–")} value={r.ce.benchmark ? usd(r.ce.benchmark.ce) : "–"}
        sub={r.ce.benchmark ? "± " + usd(r.ce.benchmark.se) : undefined} />
      <Stat label={<MetricLabel id="DCE">ΔCE vs benchmark</MetricLabel>} value={d ? signedPct(d.delta) : "–"}
        sub={d ? <>± {pct(d.se, 2)} paired SE · {d.significant ? <Badge variant="secondary">beyond 2 SE</Badge> : <Badge variant="outline">within 2 SE</Badge>}</> : undefined} />
      <Stat label={<MetricLabel id="PDEP">Depletion probability</MetricLabel>} value={r.shortfall ? pct(r.shortfall.p_depletion) : "–"}
        sub={r.shortfall ? <><MetricLabel id="CVaR">CVaR95 shortfall</MetricLabel> {num(r.shortfall.cvar95_L, 2)} · bench {pct(r.benchmark_shortfall?.p_depletion)}</> : undefined} />
    </div>
  );
}

export function ResultSummary({ r, runId, retireAge, compact = false, instance }: {
  r: ExperimentResults; runId?: string | null; retireAge?: number; compact?: boolean; instance?: string;
}) {
  const t = useVizTokens();
  const isDP = r.kind === "dp";
  const wealthKey = isDP ? "cash_on_hand" : "wealth";
  const h = compact ? 240 : 320;
  return (
    <div className="space-y-4">
      <HeadlineStats r={r} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Viz id="EX-01" instance={instance} runId={runId} cls="model_generated" title={isDP ? "Cash-on-hand fan (real $)" : undefined}>
          <FanChart ages={r.ages} q={r.fan[wealthKey]} benchmark={r.fan.benchmark_wealth} retireAge={retireAge} height={h} />
        </Viz>
        <Viz id="EX-02" instance={instance} runId={runId} cls="model_generated">
          <FanChart ages={r.ages} q={r.fan.consumption} benchmark={r.fan.benchmark_consumption} retireAge={retireAge} height={h} />
        </Viz>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Viz id="EX-03" instance={instance} runId={runId} cls="model_generated" footnote={r.policy?.label}>
          <WeightPath ages={r.ages} assets={r.weights_path.assets} weights={r.weights_path.mean} height={h - 20} allAssets={r.universe?.assets ?? r.assets} />
        </Viz>
        {r.shortfall ? (
          <Viz id="EX-04" instance={instance} runId={runId} cls="model_generated">
            <Plot height={h - 20} data={[
              { x: r.ages, y: r.shortfall.p_depleted_by_age, type: "scatter", mode: "lines", name: "Policy", line: { width: 2, color: t.series[0] }, hovertemplate: "%{y:.1%}" },
              ...(r.benchmark_shortfall ? [{ x: r.ages, y: r.benchmark_shortfall.p_depleted_by_age, type: "scatter", mode: "lines", name: "Benchmark",
                line: { width: 2, dash: "dash", color: t.series[1] }, hovertemplate: "%{y:.1%}" }] : []),
            ] as Data[]} layout={{ xaxis: { title: { text: "Age" } }, yaxis: { tickformat: ".0%", rangemode: "tozero" } }} />
          </Viz>
        ) : r.surfaces ? (
          <Viz id="EX-05" instance={instance} runId={runId} cls="model_generated">
            <Plot height={h - 20} data={r.surfaces.by_regime[0].filter((_, i) => i % 2 === 0).map((row, i) => ({
              x: r.surfaces!.x, y: row.equity, type: "scatter", mode: "lines", name: "age " + row.age, line: { width: 2, color: t.series[i % 8] } })) as Data[]}
              layout={{ xaxis: { title: { text: "x" }, type: "log" }, yaxis: { tickformat: ".0%", range: [0, 1.02] } }} />
          </Viz>
        ) : null}
      </div>
      {!compact && runId && !isDP ? (
        <Viz id="EX-06" instance={instance} runId={runId} cls="model_generated">
          <SamplePaths runId={runId} />
        </Viz>
      ) : null}
      {r.warnings && r.warnings.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {r.warnings.map((w) => <Badge key={w} variant="outline" className="text-[11px]">⚠ {w}</Badge>)}
        </div>
      ) : null}
      <Provenance meta={r.meta} runId={runId} />
    </div>
  );
}
