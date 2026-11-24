"use client";
import type { Data } from "plotly.js";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plot, useVizTokens } from "@/components/visualizations/Plot";
import { Viz } from "@/components/visualizations/VisualizationFrame";
import { MetricLabel } from "@/components/common/MetricLabel";
import { Stat } from "@/components/common/Stat";
import { num, pct, usd } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * Curve panels carried over from the original fixed-income page, now framed under the registry IDs they
 * belong to (instance-suffixed so they coexist with the study views): curve KPIs, yield-history lines,
 * the par-bond risk table with Macaulay duration, parallel-shock P&L bars with twists, and the monthly
 * 10Y return decomposition series. All read the same /v1/market/yield-curve response.
 */
export function CurveKpis({ d, years, withdrawal }: { d: any; years: number; withdrawal: number }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Curve date (last GSW observation)" value={d.date} />
      <Stat label="10Y par yield" value={pct(d.nominal.par[9], 2)} sub={"2s10s " + num((d.nominal.par[9] - d.nominal.par[1]) * 1e4, 0) + " bp"} />
      <Stat label="Liability PV (TIPS curve)" value={d.liability ? usd(d.liability.pv) : "–"} sub={d.liability ? `${years}y × ${usd(withdrawal)}` : "real curve unavailable"} />
      <Stat label={<MetricLabel id="DUR">Liability duration</MetricLabel>} value={d.liability ? num(d.liability.duration, 1) + " y" : "–"}
        sub={d.liability ? "gap vs 10Y Tsy " + num(d.liability.duration_gap_vs_10y_tsy, 1) + " y" : undefined} />
    </div>
  );
}

export function YieldHistoryLines({ d }: { d: any }) {
  const t = useVizTokens();
  return (
    <Viz id="FI-02" instance="lines" title="Yield history (2/5/10/30Y)" cls="model_generated" question="GSW zero yields, month-end, as lines.">
      <Plot height={320} data={["02y", "05y", "10y", "30y"].filter((k) => d.history[k]).map((k, i) => ({
        x: d.history.dates, y: d.history[k], type: "scatter", mode: "lines", name: k, line: { width: 1.4, color: t.series[i] } })) as Data[]}
        layout={{ yaxis: { tickformat: ".0%" } }} />
    </Viz>
  );
}

export function ParBondRiskTable({ d }: { d: any }) {
  return (
    <Viz id="FI-03" instance="par-bond" title="Par-bond risk table (Macaulay / modified / convexity / DV01)" cls="model_generated"
      question="Macaulay and modified duration, convexity and DV01 per $1 of par bonds on the selected curve.">
      <Table>
        <TableHeader><TableRow><TableHead>Maturity</TableHead><TableHead className="text-right">Par yield</TableHead><TableHead className="text-right">Mac. dur</TableHead>
          <TableHead className="text-right">Mod. dur</TableHead><TableHead className="text-right">Convexity</TableHead><TableHead className="text-right"><MetricLabel id="DV01">DV01</MetricLabel></TableHead></TableRow></TableHeader>
        <TableBody>
          {d.risk_table.map((r: any) => (
            <TableRow key={r.maturity}><TableCell>{r.maturity}Y</TableCell><TableCell className="text-right tabular-nums">{pct(r.yield, 2)}</TableCell>
              <TableCell className="text-right tabular-nums">{num(r.mac_duration)}</TableCell><TableCell className="text-right tabular-nums">{num(r.mod_duration)}</TableCell>
              <TableCell className="text-right tabular-nums">{num(r.convexity, 1)}</TableCell><TableCell className="text-right tabular-nums">{num(r.dv01, 4)}</TableCell></TableRow>
          ))}
        </TableBody>
      </Table>
    </Viz>
  );
}

export function ShockPnl({ d }: { d: any }) {
  const t = useVizTokens();
  return (
    <Viz id="FI-05" instance="pnl" title="Parallel-shock P&L (full vs approximation)" cls="model_generated"
      question="Full repricing on the zero curve (bars) vs duration + convexity approximation (markers), with steepener / flattener twists.">
      <Plot height={300} data={[2, 5, 10, 30].flatMap((m, i) => {
        const rows = d.shocks.filter((s: any) => s.maturity === m);
        return [
          { x: rows.map((r: any) => r.shock_bp), y: rows.map((r: any) => r.full), type: "bar", name: m + "Y full", marker: { color: t.series[i] }, hovertemplate: "%{y:.2%}" },
          { x: rows.map((r: any) => r.shock_bp), y: rows.map((r: any) => r.approx), type: "scatter", mode: "markers", name: m + "Y approx", showlegend: false,
            marker: { color: t.series[i], size: 8, symbol: "diamond", line: { width: 2, color: t.surface } }, hovertemplate: "approx %{y:.2%}" },
        ];
      }) as Data[]} layout={{ barmode: "group", xaxis: { title: { text: "Shock (bp)" }, type: "category" }, yaxis: { tickformat: ".0%" } }} />
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground md:grid-cols-4">
        {d.twists.map((tw: any) => <div key={tw.maturity}>{tw.maturity}Y steepener {pct(tw.steepener, 2)} · flattener {pct(tw.flattener, 2)}</div>)}
      </div>
    </Viz>
  );
}

export function DecompositionSeries({ d }: { d: any }) {
  const t = useVizTokens();
  return (
    <Viz id="FI-07" instance="monthly" title="10Y par-bond monthly return decomposition (series)" cls="model_generated"
      question="Carry + roll-down + yield change (−D·Δy) + convexity each month; residual is the approximation error.">
      <Plot height={340} data={(["carry", "roll_down", "yield_change", "convexity", "residual"] as const).map((k, i) => ({
        x: d.decomposition_10y.map((r: any) => r.date), y: d.decomposition_10y.map((r: any) => r[k]), type: "bar", name: k.replace("_", " "),
        marker: { color: t.series[i] }, hovertemplate: k + " %{y:.2%}<extra></extra>" })).concat([{
        x: d.decomposition_10y.map((r: any) => r.date), y: d.decomposition_10y.map((r: any) => r.total), type: "scatter", mode: "lines",
        name: "total", line: { width: 2, color: t.text }, marker: { color: t.text }, hovertemplate: "total %{y:.2%}<extra></extra>" } as any]) as Data[]}
        layout={{ barmode: "relative", yaxis: { tickformat: ".1%" } }} />
    </Viz>
  );
}
