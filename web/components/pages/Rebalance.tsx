"use client";
import { useState } from "react";
import { ResearchPage, Sec } from "@/components/research/page";
import { ContextBar, DataTable, Grid, Kpi, StudyGate, Viz, Warnings, dataClassOf } from "@/components/research/kit";
import { NativeSelect } from "@/components/common/Fields";
import { Bars, Fan, Forest, Heat, Lines, Scatter, Waterfall, pct, spct, useAssetColor, usd } from "@/components/visualizations/charts";
import { useTrace } from "@/lib/api/v2";

/* eslint-disable @typescript-eslint/no-explicit-any */
const SYMBOL: Record<string, string> = { none: "circle-open", calendar: "circle", band: "square", "cash-flow aware": "diamond", risk: "triangle-up" };

function TraceBlock({ runId, strategies }: { runId: string; strategies: string[] }) {
  const [strategy, setStrategy] = useState("browne_15_35");
  const [path, setPath] = useState(0);
  const tr = useTrace(runId, { strategy, path });
  const color = useAssetColor();
  const t = tr.data?.trace;
  const months = t ? t.monthly.reason.map((_: number, i: number) => i / 12) : [];
  const events = t ? t.monthly.reason.map((r: number, i: number) => ({ r, i })).filter((e: any) => e.r >= 1 && e.r <= 6) : [];
  const rows = t ? t.monthly.reason.map((r: number, i: number) => {
    const pre = t.monthly.pre_weights[i];
    const post = t.monthly.post_weights[i];
    const w = t.monthly.wealth_post_trade[i];
    return { month: i, trigger: t.reasons[r], ...Object.fromEntries(t.assets.flatMap((a: string, ai: number) => [[a + "_trade", t.monthly.trades[i][ai]], [a + "_pre", pre[ai]], [a + "_post", post[ai]]])),
      cost: t.monthly.cost[i], cf: t.monthly.funded_draw[i] - t.monthly.contribution[i], wealth: w };
  }).filter((x: any) => x.trigger !== "none") : [];
  const su = t?.sources_uses;
  return (
    <>
      <div className="flex flex-wrap items-end gap-3 text-xs">
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">strategy</span>
          <NativeSelect value={strategy} onChange={setStrategy} options={strategies.map((s) => ({ value: s, label: s }))} /></label>
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">path</span>
          <input type="number" min={0} value={path} onChange={(e) => setPath(Math.max(0, Number(e.target.value)))} className="h-8 w-24 rounded border border-input bg-transparent px-2" /></label>
        <span className="text-muted-foreground">Deterministic re-simulation from the stored spec (same seed → same path).</span>
      </div>
      <Grid>
        <Viz id="RB-02" title="Target vs actual weight paths" question="Pre-trade sleeve weights month by month against targets; ticks mark executed rebalances." runId={runId}
          definition="Solid = actual weight before the trading decision; dotted = target (reserve-adjusted when a cash buffer applies).">
          {t ? <Lines xTitle="years" yTitle="weight" yfmt=".0%" lines={t.assets.flatMap((a: string, ai: number) => [
            { name: a, color: color(a, ai), x: months, y: t.monthly.pre_weights.map((w: number[]) => w[ai]), width: 1.5 },
            { name: a + " target", color: color(a, ai), x: months, y: t.monthly.target.map((w: number[]) => w[ai]), dash: "dot", width: 1 }])}
            shapes={events.map((e: any) => ({ type: "line", x0: e.i / 12, x1: e.i / 12, yref: "paper", y0: 0, y1: 0.04, line: { width: 1, color: "#888" } }))} /> : <div className="h-72 animate-pulse rounded bg-muted/40" />}
        </Viz>
        <Viz id="RB-04" title="Sources and uses waterfall" question="Where did the money come from and go over the whole path? The residual checks the ledger." runId={runId}
          definition={su?.identity + " Market P&L is computed independently from post-trade holdings × returns; the residual is reconciliation error (rounding)."}>
          {su ? <><Waterfall yTitle="real $" labels={["start wealth", "market P&L", "contributions", "funded spending", "trading cost", "residual"]}
            values={[su.start_wealth, su.market_return_and_income, su.contributions, -su.funded_spending, -su.trading_cost, su.reconciliation_residual]} totalLabel="end wealth" />
            <div className="text-xs text-muted-foreground">asset sales {usd(su.asset_sales)} · purchases {usd(su.asset_purchases)} · reconciliation residual {usd(su.reconciliation_residual)} ({pct(Math.abs(su.reconciliation_residual) / Math.max(su.end_wealth, 1), 4)})</div></> : null}
        </Viz>
      </Grid>
      <Viz id="RB-03" title="Trade audit timeline" question="Every executed trade: date, buy/sell dollars per sleeve, cost, trigger, cash-flow funding and weights before/after." runId={runId}>
        {t ? <div className="max-h-80 overflow-auto"><DataTable rows={rows} columns={[{ key: "month", label: "month" }, { key: "trigger", label: "trigger" },
          ...t.assets.flatMap((a: string) => [{ key: a + "_trade", label: a + " $", fmt: usd }, { key: a + "_pre", label: a + " pre", fmt: (v: number) => pct(v) }, { key: a + "_post", label: a + " post", fmt: (v: number) => pct(v) }]),
          { key: "cost", label: "cost", fmt: usd }, { key: "cf", label: "net draw", fmt: usd }, { key: "wealth", label: "wealth after", fmt: usd }]} /></div> : null}
      </Viz>
    </>
  );
}

function Body({ env }: { env: any }) {
  const res = env.results;
  const runId = env.run_id as string;
  const cls = dataClassOf(res);
  const f = res.frontier as any[];
  const fams = [...new Set(f.map((r) => r.family))];
  return (
    <div className="space-y-4">
      <ContextBar items={[["Universe", res.universe.name], ["Allocation", res.allocation_label], ["Withdrawal", pct(res.withdrawal)], ["Baseline", res.baseline],
        ["Cost", res.main_cost_bps + " bps/side"], ["Paths", res.n_paths], ["Run", runId.slice(0, 10)], ["Tax", "pre-tax only (no lots)"]]} />
      <Warnings items={[...res.warnings, "Browne 15/35 bands are defined for equal 25% sleeves; on a 55/35/10 target the equity sleeve is always above 35%, so the rule trades at every review."]} />
      <Sec id="overview"><Grid>
        <Viz id="RB-01" title="Rebalancing efficiency frontier" question={"Net ΔCE vs " + res.baseline + " against annual one-way turnover; marker shape = strategy family, bars = 95% CI."}
          runId={runId} cls={cls} block="frontier" definition="Turnover counts rebalancing trades only (flows reported separately). ΔCE is net of costs on executed notional. Hover for the change in success probability."
          table={() => <DataTable rows={f.map((r) => ({ ...r, d: r.delta_ce?.delta, lo: r.delta_ce?.lo, hi: r.delta_ce?.hi, ds: r.delta_success?.diff }))} columns={[
            { key: "strategy", label: "strategy" }, { key: "family", label: "family" }, { key: "turnover_one_way_per_year", label: "turnover/yr", fmt: (v) => pct(v) },
            { key: "cost_bps_per_year", label: "cost bps/yr", fmt: (v) => v.toFixed(2) }, { key: "d", label: "ΔCE", fmt: (v) => spct(v) }, { key: "lo", label: "lo", fmt: (v) => spct(v) },
            { key: "hi", label: "hi", fmt: (v) => spct(v) }, { key: "ds", label: "Δsuccess", fmt: (v) => spct(v, 1) }, { key: "first5y_shortfall", label: "5y shortfall", fmt: (v) => pct(v) }]} />}>
          <Scatter xTitle="one-way turnover per year" yTitle={"ΔCE vs " + res.baseline} xfmt=".1%" yfmt="+.2%" pts={fams.map((fam) => {
            const rr = f.filter((r) => r.family === fam);
            return { name: fam, x: rr.map((r) => r.turnover_one_way_per_year), y: rr.map((r) => r.delta_ce?.delta ?? 0), symbol: SYMBOL[fam] ?? "circle", size: 11,
              text: rr.map((r) => r.strategy + " · Δsuccess " + spct(r.delta_success?.diff ?? 0, 1) + " · CI " + spct(r.delta_ce?.lo ?? 0) + "…" + spct(r.delta_ce?.hi ?? 0)) };
          })} shapes={[{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { dash: "dot", width: 1, color: "#888" } }]} />
          <Forest height={360} xTitle="ΔCE (95% CI)" xfmt="+.1%" rows={f.filter((r) => r.delta_ce).map((r) => ({ label: r.strategy, est: r.delta_ce.delta, lo: r.delta_ce.lo, hi: r.delta_ce.hi }))} />
        </Viz>
      </Grid></Sec>
      <Sec id="costs"><Grid>
        <Viz id="RB-05" title="Calendar × threshold × cost" question="Paired ΔCE vs buy-and-hold at the same cost, by calendar cadence and absolute band, across per-side costs." runId={runId} cls={cls}
          definition={res.heatmaps.units.x + "; z: " + res.heatmaps.units.z}>
          <Heat height={220} x={res.heatmaps.costs_bps} y={res.heatmaps.calendar.rows} z={res.heatmaps.calendar.delta} diverging xTitle="cost (bps per side)" yTitle="calendar" zTitle="ΔCE" zfmt=".2%" />
          <Heat height={200} x={res.heatmaps.costs_bps} y={res.heatmaps.bands.rows} z={res.heatmaps.bands.delta} diverging xTitle="cost (bps per side)" yTitle="band" zTitle="ΔCE" zfmt=".2%" />
        </Viz>
        <Viz id="RB-09" title="Rebalancing event statistics" question="Rebalances per year and one-way trade size per event, by strategy (5/50/95th percentiles across paths)." runId={runId} cls={cls}>
          <Bars horizontal xTitle="strategy" yTitle="rebalances per year (median)" yfmt=".2f" x={res.events.map((e: any) => e.strategy)}
            series={[{ name: "median trades/yr", y: res.events.map((e: any) => e.trades_per_year_quantiles[2]) }]} />
          <DataTable rows={res.events.map((e: any) => ({ s: e.strategy, t5: e.trades_per_year_quantiles[0], t95: e.trades_per_year_quantiles[4], sz: e.trade_size_one_way_quantiles?.[2] }))}
            columns={[{ key: "s", label: "strategy" }, { key: "t5", label: "trades/yr p05", fmt: (v) => v.toFixed(2) }, { key: "t95", label: "p95", fmt: (v) => v.toFixed(2) }, { key: "sz", label: "median size/event", fmt: (v) => pct(v, 2) }]} />
        </Viz>
        <Viz id="RB-10" title="Implementation-cost decomposition" question="Commission, spread and modelled slippage (bps/yr of wealth) and the CE drag vs the same strategy at zero cost."
          runId={runId} cls={cls} definition="Pre-tax; no after-tax labelling because no tax lots are modelled. Lost-growth drag = ΔCE(with costs vs zero cost), same paths.">
          <Bars stacked horizontal xTitle="strategy" yTitle="bps per year" yfmt=".2f" x={res.cost_decomposition.map((c: any) => c.strategy)} series={[
            { name: "commission", y: res.cost_decomposition.map((c: any) => c.commission_bps_yr) }, { name: "half spread", y: res.cost_decomposition.map((c: any) => c.spread_bps_yr) },
            { name: "slippage", y: res.cost_decomposition.map((c: any) => c.slippage_bps_yr) }]} />
          <Bars horizontal xTitle="strategy" yTitle="CE drag vs zero cost" yfmt=".2%" x={res.cost_decomposition.map((c: any) => c.strategy)} series={[{ name: "ΔCE", y: res.cost_decomposition.map((c: any) => c.ce_drag_vs_zero_cost) }]} />
        </Viz>
      </Grid></Sec>
      <Sec id="cash-flows"><Grid>
        <Viz id="RB-06" title="Cash-flow rebalance savings" question="Turnover saved by directing contributions to underweights and withdrawals from overweights (same targets, same returns)."
          runId={runId} cls={cls} definition="Per-path one-way turnover saved per year (calendar 12m with proportional flows minus cash-flow targeting); box = 5/25/50/75/95 percentiles.">
          <Bars xTitle="flow scenario" yTitle="turnover per year" yfmt=".1%" x={res.cash_flow_savings.map((c: any) => c.scenario)}
            series={[{ name: "calendar, proportional flows", y: res.cash_flow_savings.map((c: any) => c.turnover_calendar) },
              { name: "cash-flow targeting", y: res.cash_flow_savings.map((c: any) => c.turnover_cf_aware) }]} />
          <DataTable rows={res.cash_flow_savings.map((c: any) => ({ ...c, med: c.saved_quantiles[2], lo: c.saved_quantiles[0], hi: c.saved_quantiles[4] }))} columns={[
            { key: "scenario", label: "scenario" }, { key: "med", label: "median saved", fmt: (v) => pct(v, 2) }, { key: "lo", label: "p05", fmt: (v) => pct(v, 2) },
            { key: "hi", label: "p95", fmt: (v) => pct(v, 2) }, { key: "cost_saved_usd_per_year", label: "cost saved $/yr", fmt: usd }, { key: "delta_ce", label: "ΔCE", fmt: (v) => spct(v) }]} />
        </Viz>
        <Viz id="RB-08" title="Liquidity runway fan" question="Months of planned withdrawals held in T-bills across retirement, by reserve target; linked to shortfall outcomes."
          runId={runId} cls={cls} definition="Runway = T-bill holdings / desired monthly draw at each year start. Refills happen at annual rebalancing.">
          {res.runway.length ? <>
            <Fan x={res.runway[res.runway.length - 1].fan.p50.map((_: number, i: number) => i)} q={res.runway[res.runway.length - 1].fan} name={res.runway[res.runway.length - 1].reserve_years + "y reserve"}
              compare={{ q: res.runway[0].fan, name: res.runway[0].reserve_years + "y reserve" }} xTitle="years since retirement" yTitle="runway (months)" yfmt=".0f" />
            <DataTable rows={res.runway} columns={[{ key: "reserve_years", label: "reserve (y)" }, { key: "p_shortfall", label: "P(shortfall)", fmt: (v) => pct(v) },
              { key: "first10y_shortfall", label: "first-10y shortfall", fmt: (v) => pct(v) }, { key: "refills_per_year", label: "refills/yr", fmt: (v) => v.toFixed(2) }, { key: "ce", label: "CE", fmt: usd }]} />
          </> : null}
        </Viz>
        <Viz id="RB-11" title="Withdrawal funding race" question="Proportional vs cash-first vs overweight-first vs bond-ladder-first funding across withdrawal rates: funded spending and success." runId={runId} cls={cls}>
          <Lines xTitle="withdrawal rate" yTitle="P(success)" xfmt=".0%" yfmt=".0%" lines={Object.entries(res.funding_race.modes).map(([m, rows]: any) => ({ name: m, x: res.funding_race.r, y: rows.map((r: any) => r.success), mode: "lines+markers" }))} />
          <Lines height={220} xTitle="withdrawal rate" yTitle="mean funded spending (total $)" xfmt=".0%" yfmt="$,.0f" lines={Object.entries(res.funding_race.modes).map(([m, rows]: any) => ({ name: m, x: res.funding_race.r, y: rows.map((r: any) => r.funded_mean) }))} />
        </Viz>
      </Grid></Sec>
      <Sec id="rules"><Grid>
        <Viz id="RB-07" title="No-trade / trade decision breakdown" question="How often does the utility-net-of-cost rule decide to trade, and does it help out of sample?"
          runId={runId} cls={cls} empty={res.no_trade ? null : "utility_net_of_cost not in the strategy list"} definition={res.no_trade?.rule + ". " + res.no_trade?.error_rate_note}>
          {res.no_trade ? <div className="grid grid-cols-2 gap-2">
            <Kpi label="accepted decisions / path" value={res.no_trade.accepted_per_path.toFixed(1)} />
            <Kpi label="rejected (cost > gain) / path" value={res.no_trade.rejected_per_path.toFixed(1)} sub={"accept rate " + pct(res.no_trade.accept_rate)} />
            <Kpi label="holdout ΔCE vs annual calendar" value={spct(res.no_trade.holdout_delta_vs_calendar_12m.delta)} ci={"95% CI " + spct(res.no_trade.holdout_delta_vs_calendar_12m.lo) + " to " + spct(res.no_trade.holdout_delta_vs_calendar_12m.hi)} />
            <Kpi label="holdout ΔCE vs monthly" value={spct(res.no_trade.holdout_delta_vs_monthly.delta)} ci={"95% CI " + spct(res.no_trade.holdout_delta_vs_monthly.lo) + " to " + spct(res.no_trade.holdout_delta_vs_monthly.hi)} />
          </div> : null}
        </Viz>
        <Viz id="RB-12" title="Risk-budget drift" question="Ex-ante portfolio volatility of drifted weights vs target, and duration contribution over time." runId={runId} cls={cls}
          definition={res.risk_meta.estimation + ". Lagged-estimate validation: " + (res.risk_meta.validation.available ? "trailing-60m forecast vs next-12m realised vol, corr " + res.risk_meta.validation.corr.toFixed(2) + ", MAE " + pct(res.risk_meta.validation.mae, 2) : "n/a")}>
          <Lines xTitle="years since retirement" yTitle="ex-ante vol (median)" yfmt=".1%" lines={[...Object.entries(res.risk_drift).map(([k, v]: any) => ({ name: k, x: v.vol_fan.p50.map((_: number, i: number) => i), y: v.vol_fan.p50 })),
            { name: "target", x: [0, (Object.values(res.risk_drift)[0] as any)?.vol_fan.p50.length ?? 30], y: [res.risk_meta.target_vol, res.risk_meta.target_vol], dash: "dot" }]} />
          <Lines height={200} xTitle="years since retirement" yTitle="duration contribution" yfmt=".2f" lines={Object.entries(res.risk_drift).slice(0, 2).map(([k, v]: any) => ({ name: k, x: v.duration_contribution_mean.map((_: any, i: number) => i), y: v.duration_contribution_mean.map((row: number[]) => row.reduce((a, b) => a + b, 0)) }))} />
        </Viz>
      </Grid></Sec>
      <Sec id="ledger"><TraceBlock runId={runId} strategies={f.map((r) => r.strategy)} /></Sec>
    </div>
  );
}

/** Rebalancing & Execution: efficiency frontier, costs, cash-flow funding, decision rules and the executed trade ledger. */
export function Rebalance() {
  return (
    <ResearchPage page="rebalance" intro="Target allocation and spending held fixed; only the trading policy changes. Calendar, bands, Browne 15/35, cash-flow-aware funding, risk bands and a utility-net-of-cost rule, all with an executed-notional trade ledger.">
      <StudyGate kind="rebalance" title="Rebalancing study" description="16 trading strategies on a 55/35/10 target, cost grid 0–20 bps, reserve 0–3 years, 2,000 paths.">
        {(env) => <Body env={env} />}
      </StudyGate>
    </ResearchPage>
  );
}
