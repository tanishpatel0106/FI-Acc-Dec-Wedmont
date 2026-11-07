"use client";
import { useEffect, useState } from "react";
import type { Data } from "plotly.js";
import { IconPlayerPause, IconPlayerPlay, IconPlayerTrackNext, IconPlayerTrackPrev } from "@tabler/icons-react";
import { ContextBar, DataTable, Grid, StudyGate, Viz, Warnings } from "@/components/research/kit";
import { Plot, useVizTokens } from "@/components/visualizations/Plot";
import { pct, spct, usd, useAssetColor } from "@/components/visualizations/charts";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Res = any;

function vline(x: string, color: string) {
  return { type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 1, line: { width: 1, dash: "dot", color } };
}

/** Timeline control: play / pause, step, scrub, speed, jump to event. Only changes the selected index. */
function Timeline({ r, i, setI, playing, setPlaying, speed, setSpeed }: { r: Res; i: number; setI: (n: number) => void; playing: boolean;
  setPlaying: (b: boolean) => void; speed: number; setSpeed: (n: number) => void }) {
  const n = r.dates.length;
  return (
    <div className="sticky top-28 z-20 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-background/95 px-3 py-2 text-xs backdrop-blur" data-testid="replay-timeline">
      <button aria-label="Previous month" className="rounded border border-border p-1" onClick={() => setI(Math.max(0, i - 1))}><IconPlayerTrackPrev className="h-4 w-4" /></button>
      <button aria-label={playing ? "Pause" : "Play"} className="rounded border border-border p-1" onClick={() => setPlaying(!playing)}>
        {playing ? <IconPlayerPause className="h-4 w-4" /> : <IconPlayerPlay className="h-4 w-4" />}</button>
      <button aria-label="Next month" className="rounded border border-border p-1" onClick={() => setI(Math.min(n - 1, i + 1))}><IconPlayerTrackNext className="h-4 w-4" /></button>
      <input aria-label="Historical month" type="range" min={0} max={n - 1} value={i} onChange={(e) => setI(Number(e.target.value))} className="w-64" />
      <span className="font-mono font-medium" data-testid="replay-date">{r.dates[i]}</span>
      <label className="flex items-center gap-1">speed
        <select aria-label="Playback speed" value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="rounded border border-input bg-transparent px-1">
          {[1, 4, 12].map((s) => <option key={s} value={s}>{s}×</option>)}</select></label>
      <label className="flex items-center gap-1">jump to
        <select aria-label="Jump to event" value="" onChange={(e) => { const k = r.dates.findIndex((d: string) => d.startsWith(e.target.value)); if (k >= 0) setI(k); }}
          className="rounded border border-input bg-transparent px-1">
          <option value="">event…</option>
          {r.events.map((ev: any) => <option key={ev.date} value={ev.date}>{ev.date} · {ev.label}</option>)}</select></label>
    </div>
  );
}

function Body({ env }: { env: any }) {
  const r: Res = env.results;
  const runId = env.run_id as string;
  const t = useVizTokens();
  const color = useAssetColor();
  const pols = Object.keys(r.policies).filter((p) => r.policies[p].available);
  const [pol, setPol] = useState(pols.includes("lifecycle_adaptive") ? "lifecycle_adaptive" : pols[0]);
  const [bench, setBench] = useState("sixty_forty");
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(4);
  const n = r.dates.length;
  useEffect(() => {
    if (!playing) return;
    const h = window.setInterval(() => setI((k) => (k >= n - 1 ? k : k + 1)), 500 / speed);
    return () => window.clearInterval(h);
  }, [playing, speed, n]);
  const P = r.policies[pol];
  const s = P.series;
  const B = r.policies[bench]?.available ? r.policies[bench].series : null;
  const c: string[] = r.candidates;
  const used = c.filter((a, k) => s.w_post.some((w: number[]) => w[k] > 1e-4) || s.target.some((w: number[]) => w[k] > 1e-4));
  const ci = (a: string) => c.indexOf(a);
  const d = r.dates;
  const vl = [vline(d[i], t.text2)];
  const mk = r.market;
  const reasons: string[] = r.reasons;
  const trades = s.trades[i] as number[];
  const notes = s.notes[i] ?? {};
  const changed = i > 0 ? c.filter((a, k) => Math.abs(s.target[i][k] - s.target[i - 1][k]) > 1e-4) : [];
  const traded = c.filter((a, k) => Math.abs(trades[k]) > 0.5);
  const explanation = (() => {
    const parts: string[] = [];
    parts.push(i === 0 ? "Initial investment at the first target." : changed.length ? "The final target changed for " + changed.join(", ") + "." : "The final target did not change.");
    parts.push(reasons[s.reason[i]] && s.reason[i] > 0 ? "Rebalancing trigger: " + reasons[s.reason[i]] + "." : "No rebalancing trigger; the contribution of " + usd(s.contrib[i]) + " was directed toward underweight sleeves.");
    if (traded.length) parts.push("Executed trades in " + traded.join(", ") + " costing " + usd(s.cost[i]) + ".");
    if (notes.forced) parts.push(notes.forced.join("; ") + ".");
    if (s.binding[i]?.length) parts.push("Binding: " + s.binding[i].join("; ") + ".");
    return parts.join(" ");
  })();
  const rollVol = s.twr.map((_: number, k: number) => {
    if (k < 11) return null;
    const x = s.twr.slice(k - 11, k + 1);
    const mu = x.reduce((a: number, b: number) => a + b, 0) / 12;
    return Math.sqrt(x.reduce((a: number, b: number) => a + (b - mu) ** 2, 0) / 11 * 12);
  });
  const growthIdx = c.map((a, k) => (r.block_of[a] === "growth" ? k : -1)).filter((k) => k >= 0);
  const fw = r.forward?.[pol];
  const ageNow = r.investor.start_age + n / 12;
  const histAges = d.map((_: string, k: number) => r.investor.start_age + (k + 1) / 12);
  const tbl = (rows: any[]) => rows.map((x: any) => ({ policy: x.policy ?? x.ablation, ...x }));
  const expRows = (block: any[], key: string) => (block ?? []).flatMap((b: any) => (b.error ? [{ [key]: b[key] ?? b.start, policy: "–", error: b.error }]
    : Object.entries(b.results).map(([p, v]: any) => ({ [key]: b[key] ?? b.start, policy: p, ...v }))));
  const sumCols = [{ key: "policy", label: "policy" }, { key: "final_wealth", label: "final wealth", fmt: usd }, { key: "twr_annual", label: "TWR/yr", fmt: (v: any) => pct(v) },
    { key: "vol_annual", label: "vol", fmt: (v: any) => pct(v) }, { key: "max_drawdown", label: "max DD", fmt: (v: any) => pct(v) },
    { key: "turnover_annual", label: "turnover/yr", fmt: (v: any) => (v ?? 0).toFixed(2) }, { key: "total_costs", label: "costs", fmt: usd }];
  return (
    <div className="space-y-4">
      <ContextBar items={[["Investor", "age " + r.investor.start_age + " in " + d[0].slice(0, 7)], ["Start wealth", usd(r.investor.initial_wealth)], ["Salary", usd(r.investor.salary)],
        ["Saves", pct(r.investor.savings_rate, 0)], ["Retires", String(r.investor.retirement_age)], ["Universe", r.universe_mode + ": " + (r.fixed_set ?? []).join(", ")],
        ["Window", d[0] + " → " + d[n - 1]], ["Run", runId.slice(0, 10)]]} />
      <Warnings items={r.warnings} />
      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="flex items-center gap-1">Policy
          <select aria-label="Portfolio policy" value={pol} onChange={(e) => setPol(e.target.value)} className="h-7 rounded border border-input bg-transparent px-1">
            {pols.map((p) => <option key={p} value={p}>{r.policies[p].label}</option>)}</select></label>
        <label className="flex items-center gap-1">Benchmark overlay
          <select aria-label="Benchmark overlay" value={bench} onChange={(e) => setBench(e.target.value)} className="h-7 rounded border border-input bg-transparent px-1">
            {pols.map((p) => <option key={p} value={p}>{p}</option>)}</select></label>
        {Object.entries(r.policies).filter(([, v]: any) => !v.available).map(([k, v]: any) => <span key={k} className="text-muted-foreground"><code>{k}</code>: {v.reason}</span>)}
      </div>
      <Timeline r={r} i={i} setI={setI} playing={playing} setPlaying={setPlaying} speed={speed} setSpeed={setSpeed} />
      <Viz id="HR-08" runId={runId} cls="model_generated" selection={{ month: d[i], policy: pol }}>
        <div className="grid gap-3 text-xs md:grid-cols-2 xl:grid-cols-4" data-testid="decision-inspector">
          <div className="rounded border border-border p-2"><div className="mb-1 font-semibold">Investor state</div>
            <div>Age {s.salary ? (r.investor.start_age + i / 12).toFixed(1) : "–"} · salary {usd(s.salary[i])} · contribution {usd(s.contrib[i])}/mo</div>
            <div>Wealth {usd(s.wealth_post[i])} (after flows and trades) · years to retirement {Math.max(r.investor.retirement_age - r.investor.start_age - i / 12, 0).toFixed(1)}</div>
            <div>Human capital {usd(s.human_capital[i])} · PV liabilities {usd(s.pv_liabilities[i])} · funding ratio {(s.funding_ratio[i] ?? 0).toFixed(2)}</div></div>
          <div className="rounded border border-border p-2"><div className="mb-1 font-semibold">Market state (known at decision)</div>
            <div>Returns through {mk.info_last_return[i]}; CPI through {mk.info_last_cpi[i]}</div>
            <div>10Y {pct(mk.y_dgs10[i], 2)} · TIPS {pct(mk.y_dfii10[i], 2)} · infl 12m {pct(mk.infl12[i], 1)} · Baa−Aaa {pct(mk.credit_spread[i], 2)}</div>
            <div>stock–bond corr 36m {mk.corr_eq_bond_36m[i]?.toFixed(2) ?? "–"} · P(high-inflation regime) {pct(mk.p_high_inflation[i], 0)} (model fit {mk.regime_fit_end[i] ?? "–"})</div>
            <div>US equity vol 12m {pct(mk.vol_short[i]?.us_eq)} · trend 12m {spct(mk.trend[i]?.us_eq, 1)}</div></div>
          <div className="rounded border border-border p-2"><div className="mb-1 font-semibold">Allocation decision</div>
            <DataTable rows={used.map((a) => ({ a, prev: i > 0 ? s.target[i - 1][ci(a)] : null, st: s.strategic[i][ci(a)], ta: s.tactical[i][ci(a)], fi: s.target[i][ci(a)] }))}
              columns={[{ key: "a", label: "sleeve" }, { key: "prev", label: "prev target", fmt: (v) => pct(v) }, { key: "st", label: "strategic", fmt: (v) => pct(v) },
                { key: "ta", label: "tactical", fmt: (v) => spct(v, 1) }, { key: "fi", label: "final", fmt: (v) => pct(v) }]} />
            <div className="mt-1 text-muted-foreground">{Object.entries(notes).filter(([k]) => k !== "forced").map(([k, v]) => k + ": " + (typeof v === "number" ? v.toFixed(3) : String(v))).join(" · ")}</div></div>
          <div className="rounded border border-border p-2"><div className="mb-1 font-semibold">Execution</div>
            <DataTable rows={used.map((a) => ({ a, pre: s.w_pre[i][ci(a)], tr: trades[ci(a)], post: s.w_post[i][ci(a)] }))}
              columns={[{ key: "a", label: "sleeve" }, { key: "pre", label: "pre-trade", fmt: (v) => pct(v) }, { key: "tr", label: "trade $", fmt: usd }, { key: "post", label: "post-trade", fmt: (v) => pct(v) }]} />
            <div className="mt-1">Trigger: <b>{reasons[s.reason[i]] ?? "none"}</b> · cost {usd(s.cost[i])}</div></div>
        </div>
        <p className="mt-2 text-xs" data-testid="decision-explanation">{explanation}</p>
      </Viz>
      <Grid>
        <Viz id="HR-01" runId={runId} cls="model_generated" selection={{ policy: pol }}>
          <Plot height={320} data={used.map((a) => ({ x: d, y: s.w_post.map((w: number[]) => w[ci(a)]), type: "scatter", mode: "lines", stackgroup: "w", name: a,
            line: { width: 0.5, color: color(a, ci(a)) }, hovertemplate: a + " %{y:.1%}<extra></extra>" })) as Data[]}
            layout={{ yaxis: { tickformat: ".0%", range: [0, 1] }, shapes: vl as any }} />
        </Viz>
        <Viz id="HR-02" runId={runId} cls="model_generated" selection={{ month: d[i] }}>
          <Plot height={220} data={[["strategic", s.strategic[i]], ["final target", s.target[i]], ["pre-trade", s.w_pre[i]], ["post-trade", s.w_post[i]]].map(([nm, w]: any, k) => ({
            x: used, y: used.map((a) => w[ci(a)]), type: "bar", name: nm, marker: { color: t.series[k] } })) as Data[]} layout={{ barmode: "group", yaxis: { tickformat: ".0%" } }} />
          <Plot height={140} data={[{ x: d, y: s.w_pre.map((w: number[], k: number) => w.reduce((a2: number, x: number, j: number) => a2 + Math.abs(x - s.target[k][j]), 0)), type: "scatter", mode: "lines", name: "Σ|pre − target|", line: { color: t.series[0] } }] as Data[]}
            layout={{ yaxis: { tickformat: ".0%" }, shapes: vl as any }} />
        </Viz>
        <Viz id="HR-03" runId={runId} cls="model_generated">
          <Plot height={300} data={[{ x: d, y: s.wealth, name: "nominal", type: "scatter", mode: "lines", line: { color: t.series[0], width: 2 } },
            { x: d, y: s.wealth_real, name: "real (last-month $)", type: "scatter", mode: "lines", line: { color: t.series[0], dash: "dash" } },
            ...(B && bench !== pol ? [{ x: d, y: B.wealth, name: bench, type: "scatter", mode: "lines", line: { color: t.series[1], dash: "dot" } }] : [])] as Data[]}
            layout={{ yaxis: { tickformat: "$~s" }, shapes: vl as any }} />
        </Viz>
        <Viz id="HR-04" runId={runId} cls="model_generated">
          <Plot height={300} data={[{ x: d, y: s.contrib_cum.map((x: number) => x + r.investor.initial_wealth), name: "contributions", type: "scatter", mode: "lines", stackgroup: "c", line: { color: t.series[2] } },
            { x: d, y: s.gains, name: "investment gain", type: "scatter", mode: "lines", stackgroup: "c", line: { color: t.series[0] } }] as Data[]}
            layout={{ yaxis: { tickformat: "$~s" }, shapes: vl as any }} />
        </Viz>
        <Viz id="HR-05" runId={runId} cls="model_generated">
          <Plot height={230} data={[{ x: d, y: rollVol, name: "realised 12m vol", type: "scatter", mode: "lines", line: { color: t.series[0] } },
            { x: d, y: s.ex_ante_vol, name: "ex-ante vol", type: "scatter", mode: "lines", line: { color: t.series[1], dash: "dash" } },
            { x: d, y: s.drawdown, name: "drawdown", type: "scatter", mode: "lines", line: { color: t.series[7] } }] as Data[]}
            layout={{ yaxis: { tickformat: ".0%" }, shapes: vl as any }} />
          <Plot height={150} data={[{ x: used, y: used.map((a) => s.rc[i][ci(a)]), type: "bar", name: "risk contribution " + d[i], marker: { color: used.map((a) => color(a, ci(a))) } }] as Data[]}
            layout={{ yaxis: { tickformat: ".0%" }, showlegend: false }} />
        </Viz>
        <Viz id="HR-06" runId={runId} cls="observed">
          <Plot height={300} data={[["10Y yield", mk.y_dgs10], ["10Y TIPS", mk.y_dfii10], ["inflation 12m", mk.infl12], ["Baa−Aaa", mk.credit_spread],
            ["stock–bond corr 36m", mk.corr_eq_bond_36m], ["P(high-inflation)", mk.p_high_inflation]].map(([nm, y]: any, k) => ({ x: d, y, name: nm, type: "scatter", mode: "lines",
            line: { color: t.series[k], width: 1.5 } })) as Data[]}
            layout={{ shapes: [...vl, ...d.filter((_: string, k: number) => s.reason[k] > 1).map((x: string) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 0.05, line: { width: 1, color: t.text2 } }))] as any }} />
        </Viz>
        <Viz id="HR-07" runId={runId} cls="model_generated" selection={{ month: d[i] }}>
          <Plot height={260} data={used.map((a) => {
            const k = ci(a);
            const idx = d.map((_: string, m: number) => m).filter((m: number) => Math.abs(s.trades[m][k]) > 0.5 && s.reason[m] > 1);
            return { x: idx.map((m: number) => d[m]), y: idx.map(() => a), type: "scatter", mode: "markers", name: a,
              marker: { size: idx.map((m: number) => Math.min(24, 4 + Math.sqrt(Math.abs(s.trades[m][k])) / 6)), color: color(a, k),
                symbol: idx.map((m: number) => (s.trades[m][k] > 0 ? "circle" : "circle-open")) },
              customdata: idx.map((m: number) => [s.trades[m][k], s.cost[m], reasons[s.reason[m]]]),
              hovertemplate: "%{x} " + a + "<br>trade $%{customdata[0]:,.0f}<br>cost $%{customdata[1]:,.2f}<br>%{customdata[2]}<extra></extra>" };
          }) as Data[]} layout={{ hovermode: "closest", showlegend: false, shapes: vl as any }} />
          <div className="text-[11px] text-muted-foreground">{d[i]}: {traded.length ? traded.map((a) => a + " " + usd(trades[ci(a)])).join(" · ") : "no trades"} · cost {usd(s.cost[i])} · {reasons[s.reason[i]]}</div>
        </Viz>
        <Viz id="HR-09" runId={runId} cls="model_generated">
          <Plot height={300} data={[{ x: d, y: s.funding_ratio, name: "funding ratio", type: "scatter", mode: "lines", line: { color: t.series[0], width: 2 }, yaxis: "y" },
            { x: d, y: s.human_capital, name: "human capital", type: "scatter", mode: "lines", line: { color: t.series[2], dash: "dot" }, yaxis: "y2" },
            { x: d, y: s.pv_liabilities, name: "PV liabilities", type: "scatter", mode: "lines", line: { color: t.series[7], dash: "dot" }, yaxis: "y2" }] as Data[]}
            layout={{ yaxis: { title: { text: "ratio" } }, yaxis2: { overlaying: "y", side: "right", tickformat: "$~s", showgrid: false }, shapes: vl as any }} />
        </Viz>
        <Viz id="HR-10" runId={runId} cls="model_generated">
          <Plot height={220} data={pols.map((p, k) => ({ x: d, y: r.policies[p].series.wealth.map((w: number, m: number) => w / r.policies.sixty_forty.series.wealth[m]),
            name: p, type: "scatter", mode: "lines", line: { width: p === pol ? 2.5 : 1, color: t.series[k % 8] } })) as Data[]}
            layout={{ yaxis: { title: { text: "wealth / 60/40" } }, shapes: vl as any }} />
          <Plot height={180} data={pols.map((p, k) => ({ x: d, y: r.policies[p].series.w_post.map((w: number[]) => growthIdx.reduce((a2: number, j: number) => a2 + w[j], 0)),
            name: p, type: "scatter", mode: "lines", showlegend: false, line: { width: p === pol ? 2.5 : 1, color: t.series[k % 8] } })) as Data[]}
            layout={{ yaxis: { title: { text: "growth weight" }, tickformat: ".0%" } }} />
        </Viz>
        <Viz id="HR-11" runId={runId} cls="model_generated" empty={fw?.available ? null : "Not computed: no forward continuation in this run."}>
          {fw?.available ? <Plot height={320} data={[
            { x: histAges, y: s.wealth_real, name: "realised (real)", type: "scatter", mode: "lines", line: { color: t.text, width: 2 } },
            ...[[0, 4, "5–95%"], [1, 3, "25–75%"]].map(([lo, hi, nm]: any, k) => ({ x: [...fw.wealth_by_age.map((q: any) => q.age), ...fw.wealth_by_age.map((q: any) => q.age).reverse()],
              y: [...fw.wealth_by_age.map((q: any) => q.q[hi]), ...fw.wealth_by_age.map((q: any) => q.q[lo]).reverse()], fill: "toself", type: "scatter", mode: "lines", name: nm,
              line: { width: 0 }, fillcolor: k ? "rgba(57,135,229,0.30)" : "rgba(57,135,229,0.15)" })),
            { x: fw.wealth_by_age.map((q: any) => q.age), y: fw.wealth_by_age.map((q: any) => q.q[2]), name: "simulated median", type: "scatter", mode: "lines", line: { color: t.series[0] } }] as Data[]}
            layout={{ yaxis: { tickformat: "$~s" }, xaxis: { title: { text: "age" } },
              shapes: [{ type: "line", x0: ageNow, x1: ageNow, yref: "paper", y0: 0, y1: 1, line: { dash: "dash", color: t.text2 } }] as any,
              annotations: [{ x: ageNow, yref: "paper", y: 1, text: "observed | simulated", showarrow: false, yanchor: "bottom", font: { size: 10 } }] as any }} /> : null}
        </Viz>
        <Viz id="HR-12" runId={runId} cls="model_generated" empty={fw?.available ? null : "Not computed: no forward continuation in this run."}>
          {fw?.available ? <Plot height={300} data={used.map((a) => ({ x: fw.allocation_by_age.map((q: any) => q.age), y: fw.allocation_by_age.map((q: any) => q.q[a]?.[1] ?? 0),
            type: "bar", name: a, marker: { color: color(a, ci(a)) } })) as Data[]} layout={{ barmode: "stack", yaxis: { tickformat: ".0%" }, xaxis: { title: { text: "age" } } }} /> : null}
        </Viz>
      </Grid>
      <Viz id="HR-13" runId={runId} cls="model_generated">
        <DataTable rows={pols.map((p) => ({ policy: p, ...r.policies[p], f_ce: r.forward?.[p]?.ce_consumption, f_ok: r.forward?.[p]?.p_no_shortfall,
          f_cvar: r.forward?.[p]?.unmet_cvar95, f_ret: r.forward?.[p]?.wealth_at_retirement?.[2] }))}
          columns={[...sumCols, { key: "n_rebalances", label: "rebalances" }, { key: "f_ce", label: "fwd CE $/yr", fmt: usd }, { key: "f_ok", label: "P(no shortfall to 95)", fmt: (v) => pct(v) },
            { key: "f_cvar", label: "unmet CVaR95", fmt: usd }, { key: "f_ret", label: "median wealth at retirement", fmt: usd }]} />
      </Viz>
      <Grid>
        <Viz id="HR-14" runId={runId} cls="model_generated" empty={r.experiments ? null : "Not computed: experiments were disabled in this run's spec."}>
          {r.experiments ? <>
            <div className="mb-1 text-xs font-medium">Cohorts starting {d[0].slice(0, 7)}</div>
            <DataTable rows={expRows(r.experiments.cohorts, "start_age")} columns={[{ key: "start_age", label: "age" }, ...sumCols]} />
            <div className="mb-1 mt-3 text-xs font-medium">Walk-forward start years (to the latest observation)</div>
            <DataTable rows={expRows(r.experiments.start_years, "start")} columns={[{ key: "start", label: "start" }, ...sumCols]} />
            <div className="mb-1 mt-3 text-xs font-medium">Estimation windows</div>
            <DataTable rows={expRows(r.experiments.windows, "window_months")} columns={[{ key: "window_months", label: "window" }, ...sumCols]} />
          </> : null}
        </Viz>
        <Viz id="HR-15" runId={runId} cls="model_generated" empty={r.experiments ? null : "Not computed: experiments were disabled in this run's spec."}>
          {r.experiments ? <DataTable rows={tbl(r.experiments.ablations)} columns={[{ key: "ablation", label: "lifecycle policy" }, ...sumCols.slice(1),
            { key: "final_funding_ratio", label: "funding ratio", fmt: (v) => (v ?? 0).toFixed(2) }]} /> : null}
        </Viz>
      </Grid>
    </div>
  );
}

const DESC = "Preset: age 20 in January 2007, $10,000 invested, $45,000 salary with realistic growth, 15% saved, retire at 65, γ = 4, monthly decisions, 11 policies, "
  + "forward continuation to 95 and validation experiments (about 5 minutes).";

/** Lifecycle & Cash Flows › Historical Portfolio Replay. */
export function HistoricalReplay() {
  return <StudyGate kind="historical_replay" title="Historical investor replay" description={DESC} runLabel="Run the 2007 preset">{(env) => <Body env={env} />}</StudyGate>;
}

/** Compact replay views reused on other pages (same persisted run, same registry IDs, instance-suffixed). */
export function ReplayPanel({ view }: { view: "trades" | "policies" | "walkforward" | "pp" | "ablations" }) {
  return (
    <StudyGate kind="historical_replay" title="Historical investor replay" description={DESC} runLabel="Run the 2007 preset">
      {(env) => <PanelBody env={env} view={view} />}
    </StudyGate>
  );
}

function PanelBody({ env, view }: { env: any; view: string }) {
  const r: Res = env.results;
  const runId = env.run_id as string;
  const t = useVizTokens();
  const pols = Object.keys(r.policies).filter((p) => r.policies[p].available);
  const d = r.dates;
  const sumCols = [{ key: "policy", label: "policy" }, { key: "final_wealth", label: "final wealth", fmt: usd }, { key: "twr_annual", label: "TWR/yr", fmt: (v: any) => pct(v) },
    { key: "max_drawdown", label: "max DD", fmt: (v: any) => pct(v) }, { key: "turnover_annual", label: "turnover/yr", fmt: (v: any) => (v ?? 0).toFixed(2) },
    { key: "total_costs", label: "costs", fmt: usd }, { key: "n_rebalances", label: "rebalances" }];
  if (view === "trades")
    return (
      <Viz id="HR-07" instance="rebalance" runId={runId} cls="model_generated" footnote="Same investor and history for every policy; open Lifecycle › Historical Portfolio Replay for the month-by-month trace.">
        <DataTable rows={pols.map((p) => ({ policy: p, ...r.policies[p] }))} columns={sumCols} />
      </Viz>
    );
  if (view === "pp")
    return (
      <Viz id="HR-10" instance="permanent" runId={runId} cls="model_generated" footnote="Classic Permanent Portfolio (25% equity / long Treasury / gold / cash) and the generalised multi-asset all-weather portfolio are separate policies.">
        <DataTable rows={["pp_classic", "pp_multi_asset", "sixty_forty"].map((p) => ({ policy: p, ...(r.policies[p] ?? {}), final_wealth: r.policies[p]?.available ? r.policies[p].final_wealth : null,
          note: r.policies[p]?.available ? "" : r.policies[p]?.reason }))} columns={[...sumCols, { key: "note", label: "availability" }]} />
      </Viz>
    );
  if (view === "walkforward")
    return (
      <Viz id="HR-14" instance="research" runId={runId} cls="model_generated" empty={r.experiments ? null : "Not computed."}>
        {r.experiments ? <DataTable rows={(r.experiments.start_years ?? []).flatMap((b: any) => (b.error ? [] : Object.entries(b.results).map(([p, v]: any) => ({ start: b.start, policy: p, ...v }))))}
          columns={[{ key: "start", label: "start" }, ...sumCols]} /> : null}
      </Viz>
    );
  if (view === "ablations")
    return (
      <Viz id="HR-15" instance="optimize" runId={runId} cls="model_generated" empty={r.experiments ? null : "Not computed."}>
        {r.experiments ? <DataTable rows={r.experiments.ablations.map((x: any) => ({ policy: x.ablation, ...x }))} columns={sumCols} /> : null}
      </Viz>
    );
  return (
    <Viz id="HR-10" instance="compare" runId={runId} cls="model_generated">
      <Plot height={300} data={pols.map((p, k) => ({ x: d, y: r.policies[p].series.wealth.map((w: number, m: number) => w / r.policies.sixty_forty.series.wealth[m]),
        name: p, type: "scatter", mode: "lines", line: { width: 1.5, color: t.series[k % 8] } })) as Data[]} layout={{ yaxis: { title: { text: "wealth / 60/40" } } }} />
    </Viz>
  );
}
