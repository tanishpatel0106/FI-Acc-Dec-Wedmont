"use client";
import { useState } from "react";
import type { Data } from "plotly.js";
import { AnimatedTabBar } from "@/components/ui/animated-tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Plot, useVizTokens } from "@/components/charts/Plot";
import { PageHeader, Section } from "@/components/common/Section";
import { Field, NativeSelect } from "@/components/common/Fields";
import { useCatalog, useMarket } from "@/lib/api/hooks";
import { assetLabel, num, pct } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Universe = "core" | "modern";

function Loading({ q }: { q: { isLoading: boolean; error: unknown } }) {
  if (q.isLoading) return <div className="h-64 animate-pulse rounded-lg bg-muted/40" />;
  if (q.error) return <div className="text-sm text-destructive">{String((q.error as Error).message)}</div>;
  return null;
}

function Returns({ universe }: { universe: Universe }) {
  const q = useMarket("returns/summary", { universe });
  const t = useVizTokens();
  const d = q.data;
  if (!d) return <Loading q={q} />;
  const assets: string[] = d.assets;
  return (
    <div className="space-y-4">
      <Section title="Return moments" description={`Monthly data ${d.window[0]} → ${d.window[1]}; annualised. Real = CPI-deflated (NSA).`}>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sleeve</TableHead>
                <TableHead className="text-right">Mean (nom)</TableHead>
                <TableHead className="text-right">Mean (real)</TableHead>
                <TableHead className="text-right">Geo (real)</TableHead>
                <TableHead className="text-right">Vol</TableHead>
                <TableHead className="text-right">Skew</TableHead>
                <TableHead className="text-right">Kurtosis</TableHead>
                <TableHead className="text-right">Max DD (real)</TableHead>
                <TableHead className="text-right">Sharpe</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.rows.map((r: any) => (
                <TableRow key={r.asset}>
                  <TableCell>{r.label}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.mean_nominal, 2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.mean_real, 2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.geo_real, 2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.vol, 2)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.skew)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.kurtosis)}</TableCell>
                  <TableCell className="text-right tabular-nums">{pct(r.max_drawdown_real, 1)}</TableCell>
                  <TableCell className="text-right tabular-nums">{num(r.sharpe)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        {Object.keys(d.excluded ?? {}).length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
            {Object.entries(d.excluded).map(([k, v]) => (
              <Badge key={k} variant="outline">{assetLabel(k)} excluded: {String(v)}</Badge>
            ))}
          </div>
        ) : null}
      </Section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Real drawdowns" description="Peak-to-trough of the real wealth index, by sleeve.">
          <Plot height={300} data={assets.map((a, i) => ({ x: d.dates, y: d.drawdowns[a], type: "scatter", mode: "lines",
            name: assetLabel(a), line: { width: 1.5, color: t.series[i % 8] }, hovertemplate: "%{y:.1%}" })) as Data[]}
            layout={{ yaxis: { tickformat: ".0%" } }} />
        </Section>
        <Section title="Rolling 36-month volatility" description="Annualised, nominal returns.">
          <Plot height={300} data={assets.map((a, i) => ({ x: d.dates, y: d.rolling_vol_36m[a], type: "scatter", mode: "lines",
            name: assetLabel(a), line: { width: 1.5, color: t.series[i % 8] }, hovertemplate: "%{y:.1%}" })) as Data[]}
            layout={{ yaxis: { tickformat: ".0%" } }} />
        </Section>
      </div>
      <Section title="Real-return correlation (full window)">
        <Plot height={360} data={[{ type: "heatmap", x: assets.map(assetLabel), y: assets.map(assetLabel), z: d.correlation.matrix,
          zmin: -1, zmax: 1, colorscale: [[0, t.divNeg], [0.5, t.divMid], [1, t.divPos]], xgap: 2, ygap: 2,
          texttemplate: "%{z:.2f}", hovertemplate: "%{y} / %{x}: %{z:.2f}<extra></extra>" } as Data]}
          layout={{ hovermode: "closest", margin: { l: 110, b: 90, t: 10, r: 10 } }} />
      </Section>
    </div>
  );
}

function Dependence({ universe, assets }: { universe: Universe; assets: string[] }) {
  const [a, setA] = useState("us_eq");
  const [b, setB] = useState("ust_10y");
  const q = useMarket("dependence", { universe, a, b });
  const t = useVizTokens();
  const d = q.data;
  const opts = assets.map((x) => ({ value: x, label: assetLabel(x) }));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Field label="Asset A"><NativeSelect value={a} onChange={setA} options={opts} /></Field>
        <Field label="Asset B"><NativeSelect value={b} onChange={setB} options={opts} /></Field>
      </div>
      {!d ? <Loading q={q} /> : (
        <>
          <Section title={`Rolling correlation: ${assetLabel(a)} vs ${assetLabel(b)}`}
            description={`Pearson on 12/36/60-month windows and DCC-GARCH(1,1) (a=${num(d.dcc.a, 3)}, b=${num(d.dcc.b, 3)}). Dotted lines: PELT change points.`}>
            <Plot height={340} data={[
              ...(["12", "36", "60"] as const).map((w, i) => ({ x: d.dates, y: d.rolling[w], type: "scatter", mode: "lines",
                name: w + "m rolling", line: { width: i === 1 ? 2 : 1.2, color: t.series[i] } })),
              { x: d.dates, y: d.dcc.corr, type: "scatter", mode: "lines", name: "DCC", line: { width: 1.2, color: t.series[6] } },
            ] as Data[]}
              layout={{ yaxis: { range: [-1, 1] }, shapes: d.change_points.dates.map((x: string) => ({ type: "line", x0: x, x1: x, yref: "paper",
                y0: 0, y1: 1, line: { color: t.text2, width: 1, dash: "dot" } })) }} />
          </Section>
          <div className="grid gap-4 lg:grid-cols-3">
            <Section title="Joint-loss frequency by decade" description="P(both below their 10% quantile); independence = 1%.">
              <Plot height={260} data={[{ type: "bar", x: Object.keys(d.by_decade), y: Object.values(d.by_decade).map((v: any) => v.joint_loss),
                marker: { color: t.series[0] }, hovertemplate: "%{x}: %{y:.1%}<extra></extra>", name: "joint loss" }]}
                layout={{ yaxis: { tickformat: ".0%" }, hovermode: "closest", showlegend: false,
                  shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0.01, y1: 0.01, line: { color: t.text2, dash: "dot", width: 1 } }] }} />
            </Section>
            <Section title="Inflation-regime conditioning" description="YoY CPI above vs below 3%.">
              <Table>
                <TableHeader><TableRow><TableHead>Regime</TableHead><TableHead className="text-right">Corr</TableHead><TableHead className="text-right">Joint loss</TableHead><TableHead className="text-right">Months</TableHead></TableRow></TableHeader>
                <TableBody>
                  {Object.entries(d.joint_loss_by_inflation).map(([k, v]: [string, any]) => (
                    <TableRow key={k}><TableCell>{k.replace("_", " ")}</TableCell><TableCell className="text-right tabular-nums">{num(v.corr)}</TableCell>
                      <TableCell className="text-right tabular-nums">{pct(v.joint_loss)}</TableCell><TableCell className="text-right tabular-nums">{v.n}</TableCell></TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-3 text-xs text-muted-foreground">Full-sample correlation {num(d.full_sample_corr)}</div>
            </Section>
            <Section title="Student-t copula tails" description="Kendall-τ ρ, ν by profile ML; λ = lower-tail dependence.">
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><div className="text-xs text-muted-foreground">ρ</div><div className="tabular-nums">{num(d.t_copula.rho, 3)}</div></div>
                <div><div className="text-xs text-muted-foreground">ν</div><div className="tabular-nums">{num(d.t_copula.nu, 1)}</div></div>
                <div><div className="text-xs text-muted-foreground">λ tail</div><div className="tabular-nums">{num(d.t_copula.tail_dependence, 3)}</div></div>
                <div><div className="text-xs text-muted-foreground">Kendall τ</div><div className="tabular-nums">{num(d.t_copula.kendall_tau, 3)}</div></div>
              </div>
            </Section>
          </div>
          <Section title="Out-of-sample covariance forecasts" description={"One-month-ahead forecasts scored on unseen months (lower QLIKE is better). " + d.caveat}>
            <Table>
              <TableHeader><TableRow><TableHead>Model</TableHead><TableHead className="text-right">QLIKE</TableHead><TableHead className="text-right">Realised min-var vol</TableHead></TableRow></TableHeader>
              <TableBody>
                {d.forecast_comparison.map((r: any) => (
                  <TableRow key={r.model}><TableCell>{r.model}</TableCell><TableCell className="text-right tabular-nums">{num(r.qlike, 3)}</TableCell>
                    <TableCell className="text-right tabular-nums">{pct(r.minvar_vol, 2)}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          </Section>
        </>
      )}
    </div>
  );
}

function Regimes({ universe }: { universe: Universe }) {
  const [k, setK] = useState("2");
  const [kind, setKind] = useState<"filtered" | "smoothed">("filtered");
  const q = useMarket("regimes", { universe, k: Number(k) });
  const t = useVizTokens();
  const d = q.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <Field label="Regimes K"><NativeSelect value={k} onChange={setK} options={[{ value: "2", label: "K = 2" }, { value: "3", label: "K = 3" }]} /></Field>
        <Field label="Probabilities"><NativeSelect value={kind} onChange={setKind} options={[{ value: "filtered", label: "Filtered (decisions)" }, { value: "smoothed", label: "Smoothed (description)" }]} /></Field>
      </div>
      {!d ? <Loading q={q} /> : (
        <>
          <Section title="Regime probabilities" description={d.note}>
            <Plot height={300} data={[
              ...d.names.map((n: string, s: number) => ({ x: d.dates, y: d[kind].map((r: number[]) => r[s]), type: "scatter", mode: "lines",
                stackgroup: "p", name: `${s}: ${n}`, line: { width: 0.5, color: t.series[s] }, fillcolor: t.series[s] })),
              ...(d.usrec ? [{ x: d.dates, y: d.usrec, type: "scatter", mode: "lines", name: "NBER recession (retrospective)",
                line: { width: 1, color: t.text2, shape: "hv" }, yaxis: "y" }] : []),
            ] as Data[]} layout={{ yaxis: { range: [0, 1], tickformat: ".0%" } }} />
          </Section>
          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Regime means (annualised, real) and volatility">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader><TableRow><TableHead>Series</TableHead>{d.names.map((n: string, s: number) => <TableHead key={s} className="text-right">{s}: μ / σ</TableHead>)}</TableRow></TableHeader>
                  <TableBody>
                    {d.series.map((name: string, j: number) => (
                      <TableRow key={name}><TableCell>{name === "inflation" ? "CPI inflation" : assetLabel(name)}</TableCell>
                        {d.names.map((_: string, s: number) => <TableCell key={s} className="text-right tabular-nums">{pct(d.mu_annual[s][j], 1)} / {pct(d.vol_annual[s][j], 1)}</TableCell>)}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </Section>
            <Section title="Transition matrix & model selection" description="Labels are assigned after inspecting μ_s and Σ_s; K chosen by BIC and interpretability.">
              <Table>
                <TableHeader><TableRow><TableHead>From \ to</TableHead>{d.names.map((_: string, s: number) => <TableHead key={s} className="text-right">{s}</TableHead>)}<TableHead className="text-right">E[duration]</TableHead></TableRow></TableHeader>
                <TableBody>
                  {d.transition.map((row: number[], i: number) => (
                    <TableRow key={i}><TableCell>{i}: {d.names[i]}</TableCell>{row.map((v, j) => <TableCell key={j} className="text-right tabular-nums">{num(v, 3)}</TableCell>)}
                      <TableCell className="text-right tabular-nums">{num(d.expected_duration_months[i], 0)} m</TableCell></TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="mt-3 flex gap-4 text-xs text-muted-foreground">
                {Object.entries(d.bic).map(([kk, v]) => <span key={kk}>BIC K={kk}: <span className="tabular-nums">{num(v as number, 0)}</span></span>)}
              </div>
            </Section>
          </div>
        </>
      )}
    </div>
  );
}

function Factors({ universe }: { universe: Universe }) {
  const q = useMarket("factors", { universe });
  const d = q.data;
  if (!d) return <Loading q={q} />;
  return (
    <Section title="Factor exposures" description="OLS of monthly excess returns on Fama–French factors (Mkt-RF, SMB, HML, RMW, CMA, UMD) over each sleeve's overlap.">
      <div className="overflow-x-auto">
        <Table>
          <TableHeader><TableRow><TableHead>Sleeve</TableHead><TableHead className="text-right">α (ann.)</TableHead><TableHead className="text-right">t(α)</TableHead>
            {d.factors.map((f: string) => <TableHead key={f} className="text-right">β {f}</TableHead>)}<TableHead className="text-right">R²</TableHead><TableHead className="text-right">n</TableHead></TableRow></TableHeader>
          <TableBody>
            {d.rows.map((r: any) => (
              <TableRow key={r.asset}><TableCell>{assetLabel(r.asset)}</TableCell><TableCell className="text-right tabular-nums">{pct(r.alpha_annual, 2)}</TableCell>
                <TableCell className="text-right tabular-nums">{num(r.alpha_t)}</TableCell>
                {d.factors.map((f: string) => <TableCell key={f} className="text-right tabular-nums">{num(r.betas[f])}</TableCell>)}
                <TableCell className="text-right tabular-nums">{num(r.r2)}</TableCell><TableCell className="text-right tabular-nums">{r.n}</TableCell></TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Section>
  );
}

export function ResearchLab() {
  const [tab, setTab] = useState("returns");
  const [universe, setUniverse] = useState<Universe>("core");
  const cat = useCatalog();
  const assets: string[] = cat.data?.universes?.[universe]?.assets ?? ["us_eq", "ust_10y", "tbill"];
  return (
    <div>
      <PageHeader eyebrow="01" title="Multi-Asset Research Lab"
        description="Has stock–bond diversification structurally changed? Several definitions of dependence, conditional on inflation regimes, scored out of sample.">
        <Field label="Universe">
          <NativeSelect value={universe} onChange={setUniverse} options={[{ value: "core", label: "Long-history core" }, { value: "modern", label: "Modern diversified" }]} />
        </Field>
      </PageHeader>
      <AnimatedTabBar className="mb-5" value={tab} onChange={setTab} tabs={[
        { title: "Returns", value: "returns" }, { title: "Dependence", value: "dependence" },
        { title: "Regimes", value: "regimes" }, { title: "Factors", value: "factors" }]} />
      {tab === "returns" ? <Returns universe={universe} /> : null}
      {tab === "dependence" ? <Dependence universe={universe} assets={assets} /> : null}
      {tab === "regimes" ? <Regimes universe={universe} /> : null}
      {tab === "factors" ? <Factors universe={universe} /> : null}
    </div>
  );
}
