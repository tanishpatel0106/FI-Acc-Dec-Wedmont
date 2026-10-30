"use client";
import { useState } from "react";
import type { Data } from "plotly.js";
import { AnimatedTabBar } from "@/components/ui/animated-tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plot, useVizTokens } from "@/components/charts/Plot";
import { PageHeader, Section } from "@/components/common/Section";
import { Field, NumberInput } from "@/components/common/Fields";
import { MetricLabel } from "@/components/common/MetricLabel";
import { Stat } from "@/components/common/Stat";
import { useMarket } from "@/lib/api/hooks";
import { num, pct, usd } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any */
export function FixedIncome() {
  const [date, setDate] = useState("");
  const [withdrawal, setWithdrawal] = useState(40000);
  const [years, setYears] = useState(30);
  const [tab, setTab] = useState("curve");
  const q = useMarket("yield-curve", { date: date || undefined, withdrawal, years });
  const t = useVizTokens();
  const d = q.data;
  return (
    <div>
      <PageHeader eyebrow="M2" title="Fixed Income panel"
        description="GSW fitted nominal and TIPS real curves, PCA of yield changes, duration / DV01 / convexity, rate-shock P&L and the real liability of a withdrawal stream.">
        <div className="flex flex-wrap gap-3">
          <Field label="Curve date (month-end)"><input type="month" value={date ? date.slice(0, 7) : ""} onChange={(e) => setDate(e.target.value ? e.target.value + "-28" : "")}
            className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm dark:bg-input/30" /></Field>
          <Field label="Real withdrawal / yr"><NumberInput value={withdrawal} step={5000} onChange={setWithdrawal} /></Field>
          <Field label="Years"><NumberInput value={years} step={1} min={1} max={60} onChange={setYears} /></Field>
        </div>
      </PageHeader>
      {q.isLoading ? <div className="h-80 animate-pulse rounded-xl bg-muted/40" /> : null}
      {q.error ? <div className="text-sm text-destructive">{String((q.error as Error).message)}</div> : null}
      {d ? (
        <>
          <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Curve date" value={d.date} />
            <Stat label="10Y par yield" value={pct(d.nominal.par[9], 2)} sub={"2s10s " + num((d.nominal.par[9] - d.nominal.par[1]) * 1e4, 0) + " bp"} />
            <Stat label="Liability PV (TIPS curve)" value={d.liability ? usd(d.liability.pv) : "–"} sub={d.liability ? `${years}y × ${usd(withdrawal)}` : "real curve unavailable"} />
            <Stat label="Liability duration" value={d.liability ? num(d.liability.duration, 1) + " y" : "–"}
              sub={d.liability ? "gap vs 10Y Tsy " + num(d.liability.duration_gap_vs_10y_tsy, 1) + " y" : undefined} />
          </div>
          <AnimatedTabBar className="mb-4" value={tab} onChange={setTab} tabs={[
            { title: "Curve explorer", value: "curve" }, { title: "PCA", value: "pca" },
            { title: "Duration & shocks", value: "risk" }, { title: "Return decomposition", value: "decomp" }]} />
          {tab === "curve" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Section title="Zero-coupon curves" description="GSW continuously-compounded zero yields; dashed = one year earlier.">
                <Plot height={320} data={[
                  { x: d.nominal.maturities, y: d.nominal.zero, type: "scatter", mode: "lines+markers", name: "Nominal " + d.date, line: { width: 2, color: t.series[0] }, marker: { size: 5 } },
                  { x: d.nominal_1y_ago.maturities, y: d.nominal_1y_ago.zero, type: "scatter", mode: "lines", name: "Nominal " + d.nominal_1y_ago.date, line: { width: 1.5, dash: "dash", color: t.series[0] } },
                  ...(d.real ? [{ x: d.real.maturities, y: d.real.zero, type: "scatter", mode: "lines+markers", name: "TIPS real", line: { width: 2, color: t.series[1] }, marker: { size: 5 } }] : []),
                ] as Data[]} layout={{ xaxis: { title: { text: "Maturity (years)" } }, yaxis: { tickformat: ".1%" } }} />
              </Section>
              <Section title="Yield history" description="GSW zero yields, month-end.">
                <Plot height={320} data={["02y", "05y", "10y", "30y"].filter((k) => d.history[k]).map((k, i) => ({
                  x: d.history.dates, y: d.history[k], type: "scatter", mode: "lines", name: k, line: { width: 1.4, color: t.series[i] } })) as Data[]}
                  layout={{ yaxis: { tickformat: ".0%" } }} />
              </Section>
            </div>
          ) : null}
          {tab === "pca" ? (
            <Section title="PCA of monthly yield changes" description={`Window ${d.pca.window[0]} → ${d.pca.window[1]}. Labels assigned only after checking loadings.`}>
              <Plot height={340} data={d.pca.loadings.map((l: number[], i: number) => ({ x: d.pca.maturities, y: l, type: "scatter", mode: "lines+markers",
                name: `${d.pca.labels[i]} (${pct(d.pca.explained[i], 1)})`, line: { width: 2, color: t.series[i] }, marker: { size: 6 } })) as Data[]}
                layout={{ xaxis: { title: { text: "Maturity (years)" } }, yaxis: { title: { text: "Loading" } } }} />
            </Section>
          ) : null}
          {tab === "risk" ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <Section title={<MetricLabel id="DUR">Par-bond risk table</MetricLabel>}>
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
              </Section>
              <Section title="Parallel-shock P&L" description="Full repricing on the zero curve (bars) vs duration + convexity approximation (markers).">
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
              </Section>
            </div>
          ) : null}
          {tab === "decomp" ? (
            <Section title="10Y par-bond monthly return decomposition" description="Carry + roll-down + yield change (−D·Δy) + convexity; residual is the approximation error.">
              <Plot height={340} data={(["carry", "roll_down", "yield_change", "convexity", "residual"] as const).map((k, i) => ({
                x: d.decomposition_10y.map((r: any) => r.date), y: d.decomposition_10y.map((r: any) => r[k]), type: "bar", name: k.replace("_", " "),
                marker: { color: t.series[i] }, hovertemplate: k + " %{y:.2%}<extra></extra>" })).concat([{
                x: d.decomposition_10y.map((r: any) => r.date), y: d.decomposition_10y.map((r: any) => r.total), type: "scatter", mode: "lines",
                name: "total", line: { width: 2, color: t.text }, marker: { color: t.text }, hovertemplate: "total %{y:.2%}<extra></extra>" } as any]) as Data[]}
                layout={{ barmode: "relative", yaxis: { tickformat: ".1%" } }} />
            </Section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
