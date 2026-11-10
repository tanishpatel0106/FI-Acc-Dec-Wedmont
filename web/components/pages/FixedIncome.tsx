"use client";
import { useState } from "react";
import { CurveKpis, DecompositionSeries, ParBondRiskTable, ShockPnl, YieldHistoryLines } from "@/components/research/fixed-income/CurvePanels";
import { DataTable, Empty, Grid, Kpi, Viz } from "@/components/research/kit";
import { ResearchPage, Sec } from "@/components/research/page";
import { Bars, Heat, Lines, Waterfall, pct, usd } from "@/components/visualizations/charts";
import { useMarket } from "@/lib/api/hooks";
import { useStudyLatest, useV2 } from "@/lib/api/v2";

/* eslint-disable @typescript-eslint/no-explicit-any */
const bp = (v: number) => (v * 1e4).toFixed(0) + "bp";

function Body() {
  const [date, setDate] = useState<string>("");
  const [withdrawal, setWithdrawal] = useState(40000);
  const [years, setYears] = useState(30);
  const [budget, setBudget] = useState(1_000_000);
  const [pension, setPension] = useState(0);
  const d = date || undefined;
  const yc = useMarket("yield-curve", { date: d, withdrawal, years });
  const kr = useV2("/v1/fixed-income/key-rates", { date: d, withdrawal, years });
  const tw = useV2("/v1/fixed-income/twist", { date: d });
  const ty = useV2("/v1/fixed-income/taylor", { date: d });
  const lg = useV2("/v1/fixed-income/liability-gap", { date: d, withdrawal, years, pension });
  const ld = useV2("/v1/fixed-income/ladder", { date: d, withdrawal, years, budget });
  const co = useV2("/v1/fixed-income/coloss");
  const cr = useV2("/v1/fixed-income/credit");
  const fr = useStudyLatest("frontier");
  const y = yc.data;
  const [shock, setShock] = useState(100);
  const hist = y?.history;
  const frRes = fr.data?.status === "done" ? fr.data.results : null;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card px-3 py-2 text-xs">
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">curve date (month end; blank = latest)</span>
          <input type="month" value={date} onChange={(e) => setDate(e.target.value)} className="h-8 rounded border border-input bg-transparent px-2" /></label>
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">annual real withdrawal $</span>
          <input type="number" step={5000} value={withdrawal} onChange={(e) => setWithdrawal(Number(e.target.value))} className="h-8 w-28 rounded border border-input bg-transparent px-2" /></label>
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">years</span>
          <input type="number" min={5} max={40} value={years} onChange={(e) => setYears(Number(e.target.value))} className="h-8 w-20 rounded border border-input bg-transparent px-2" /></label>
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">pension offset $</span>
          <input type="number" step={5000} value={pension} onChange={(e) => setPension(Number(e.target.value))} className="h-8 w-28 rounded border border-input bg-transparent px-2" /></label>
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">ladder budget $</span>
          <input type="number" step={50000} value={budget} onChange={(e) => setBudget(Number(e.target.value))} className="h-8 w-32 rounded border border-input bg-transparent px-2" /></label>
        <span className="text-muted-foreground">Units: % annual yield (GSW continuously-compounded zero; derived par), bp, % total return, USD DV01. Curves are monthly model fits (model_generated), not quotes.</span>
      </div>
      {y ? <CurveKpis d={y} years={years} withdrawal={withdrawal} /> : null}
      <Sec id="curves"><Grid>
        <Viz id="FI-01" title="Nominal / real Treasury yield curves" question={"Zero and par curves at " + (y?.date ?? "…") + " with the curve one year earlier and the TIPS real curve."}
          cls="model_generated" definition="Fed GSW (Gürkaynak–Sack–Wright) fitted zero curves; par yields derived from zeros. Basis: continuously compounded zero, semi-annual par.">
          {y ? <Lines xTitle="maturity (years)" yTitle="yield" yfmt=".2%" lines={[
            { name: "nominal zero " + y.date, x: y.nominal.maturities, y: y.nominal.zero }, { name: "nominal par", x: Object.keys(y.nominal.par ?? {}).length ? y.nominal.maturities : [], y: y.nominal.par, dash: "dash" },
            { name: "nominal zero " + y.nominal_1y_ago.date, x: y.nominal_1y_ago.maturities, y: y.nominal_1y_ago.zero, dash: "dot" },
            ...(y.real ? [{ name: "TIPS real zero " + y.real.date, x: y.real.maturities, y: y.real.zero }] : [])]} /> : <div className="h-72 animate-pulse rounded bg-muted/40" />}
        </Viz>
        <Viz id="FI-02" title="Yield-curve evolution" question="2/5/10/30Y yields over time (rows = tenor). Monthly GSW observations." cls="model_generated">
          {hist ? <Heat height={260} x={hist.dates.filter((_: string, i: number) => i % 3 === 0)} y={["02y", "05y", "10y", "30y"]} xTitle="month" yTitle="tenor" zTitle="yield" zfmt=".1%" text={false}
            z={["02y", "05y", "10y", "30y"].map((k) => (hist[k] ?? []).filter((_: number, i: number) => i % 3 === 0))} /> : null}
        </Viz>
        {y ? <YieldHistoryLines d={y} /> : null}
        <Viz id="FI-08" title="Treasury curve factor PCA" question="Loadings across maturity, explained variance, sign conventions and training period; labels only if the loadings support them." cls="model_generated"
          definition="Sign convention: factor 1 positive on average; factor 2 increasing in maturity; factor 3 positive mid-curve. 'level/slope/curvature' labels are assigned only when the loadings pass those shape checks.">
          {y?.pca ? <><Lines xTitle="maturity (years)" yTitle="loading" yfmt=".2f" lines={y.pca.loadings.map((l: number[], i: number) => ({ name: y.pca.labels[i] + " (" + pct(y.pca.explained[i], 1) + ")", x: y.pca.maturities, y: l, mode: "lines+markers" }))} />
            <div className="text-[11px] text-muted-foreground">trained {y.pca.window.join(" → ")} on monthly yield changes</div></> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="risk"><Grid>
        <Viz id="FI-03" title="Duration / DV01 / convexity" question="Per-instrument risk for Treasury par bonds on the selected curve; DV01 per $1m, 1bp." cls="model_generated">
          {kr.data ? <DataTable rows={kr.data.rows} columns={[{ key: "instrument", label: "instrument" }, { key: "yield", label: "par yield", fmt: (v) => pct(v, 2) },
            { key: "modified_duration", label: "mod. duration", fmt: (v) => v.toFixed(2) }, { key: "parallel_effective_duration", label: "effective duration", fmt: (v) => v.toFixed(2) },
            { key: "convexity", label: "convexity", fmt: (v) => v.toFixed(1) }, { key: "dv01_per_1m", label: "DV01 / $1m", fmt: usd }]} /> : null}
          {y?.risk_table ? <div className="mt-2 text-[11px] text-muted-foreground">Shock preset: {[-100, -50, 50, 100, 200].map((s) => <button key={s} onClick={() => setShock(s)} className={"mr-1 rounded border px-1 " + (shock === s ? "border-foreground/40" : "border-border")}>{s}bp</button>)}
            {kr.data ? <div className="mt-1">10Y P&L at {shock}bp ≈ {usd(-kr.data.rows[2].dv01_per_1m * shock)} per $1m (DV01 linear; see FI-05 for convexity).</div> : null}</div> : null}
        </Viz>
        {y ? <ParBondRiskTable d={y} /> : null}
        <Viz id="FI-04" title="Key-rate duration bars" question="2/5/10/20/30y key-rate durations of an illustrative 10/20/40/30 ladder vs a level withdrawal liability; gap = portfolio − liability."
          cls="model_generated" definition={kr.data?.check + ". Liability: " + kr.data?.liability.definition}>
          {kr.data ? <Bars xTitle="key rate" yTitle="key-rate duration" yfmt=".2f" x={kr.data.keys.map((k: number) => k + "y")} series={[
            { name: "portfolio", y: kr.data.keys.map((k: number) => kr.data.portfolio.krd[String(k)]) }, { name: "liability", y: kr.data.keys.map((k: number) => kr.data.liability.krd[String(k)]) },
            { name: "gap", y: kr.data.keys.map((k: number) => kr.data.portfolio.gap_vs_liability[String(k)]) }]} /> : null}
          {kr.data ? <div className="text-[11px] text-muted-foreground">Check: 10Y bond Σ KRD = {kr.data.rows[2].sum_krd.toFixed(3)} vs effective duration {kr.data.rows[2].parallel_effective_duration.toFixed(3)}</div> : null}
        </Viz>
        <Viz id="FI-05" title="Full repricing vs Taylor approximation" question="Parallel-shock P&L by maturity, full repricing on the zero curve vs duration + convexity, with approximation error."
          cls="model_generated" table={() => <DataTable rows={ty.data?.rows ?? []} columns={[{ key: "maturity", label: "maturity" }, { key: "shock_bp", label: "shock bp" },
            { key: "full", label: "full", fmt: (v) => pct(v, 2) }, { key: "approx", label: "Taylor", fmt: (v) => pct(v, 2) }, { key: "error_bp", label: "error bp", fmt: (v) => v.toFixed(1) }]} />}>
          {ty.data ? <Lines xTitle="parallel shock (bp)" yTitle="approximation error (bp of price)" yfmt=".1f" lines={[2, 5, 10, 30].map((m) => {
            const rows = ty.data.rows.filter((r: any) => r.maturity === m);
            return { name: m + "Y", x: rows.map((r: any) => r.shock_bp), y: rows.map((r: any) => r.error_bp), mode: "lines+markers" };
          })} /> : null}
        </Viz>
        {y ? <ShockPnl d={y} /> : null}
        <Viz id="FI-06" title="Bear steepener / bull flattener shock grid" question="10Y price response to independent short-end and long-end moves (pivot 5y); nominal and TIPS." cls="model_generated">
          {tw.data ? <>
            <Heat height={230} x={tw.data.long_moves_bp} y={tw.data.short_moves_bp} z={tw.data.nominal_10y} diverging xTitle="long-end move (bp)" yTitle="short-end move (bp)" zTitle="nominal 10Y" zfmt=".1%" />
            {tw.data.tips_10y_real ? <Heat height={230} x={tw.data.long_moves_bp} y={tw.data.short_moves_bp} z={tw.data.tips_10y_real} diverging xTitle="long-end real move (bp)" yTitle="short-end real move (bp)" zTitle="TIPS 10Y" zfmt=".1%" /> : null}
          </> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="returns"><Grid>
        <Viz id="FI-07" title="Bond return decomposition" question="Last month's 10Y par-bond return split into carry, roll-down, yield change and convexity, with the residual disclosed." cls="model_generated">
          {y?.decomposition_10y?.length ? (() => { const dd = y.decomposition_10y[y.decomposition_10y.length - 1];
            return <><Waterfall yTitle="monthly return" yfmt=".2%" labels={["carry", "roll-down", "yield change", "convexity", "residual"]}
              values={[dd.carry, dd.roll_down, dd.yield_change, dd.convexity, dd.residual]} totalLabel={"total " + dd.date} />
              <Lines height={200} xTitle="month" yTitle="return" yfmt=".1%" lines={["carry", "roll_down", "yield_change"].map((k) => ({ name: k, x: y.decomposition_10y.map((r: any) => r.date), y: y.decomposition_10y.map((r: any) => r[k]) }))} /></>;
          })() : null}
        </Viz>
        {y?.decomposition_10y?.length ? <DecompositionSeries d={y} /> : null}
        <Viz id="FI-12" title="Bond value across the withdrawal spectrum" question="Change in survival and CE from a 40% sleeve in each instrument vs all-equity, across withdrawal rates (paired)."
          cls="model_generated" runId={fr.data?.run_id} empty={frRes ? null : "Needs a completed bond-frontier study (Withdrawal Lab)."}>
          {frRes ? <><Lines xTitle="withdrawal rate" yTitle="Δ success" xfmt=".1%" yfmt="+.0%" lines={frRes.bond_spectrum.filter((b: any) => b.available).map((b: any) => ({ name: b.bond, x: b.r, y: b.d_success, mode: "lines+markers" }))} />
            <Heat height={200} x={frRes.bond_spectrum.find((b: any) => b.available)?.r ?? []} y={frRes.bond_spectrum.filter((b: any) => b.available).map((b: any) => b.bond)}
              z={frRes.bond_spectrum.filter((b: any) => b.available).map((b: any) => b.d_ce)} diverging xTitle="withdrawal rate" yTitle="instrument" zTitle="ΔCE" zfmt=".1%" xfmt={(v) => pct(v, 1)} /></> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="liabilities"><Grid>
        <Viz id="FI-10" title="Real liability PV and duration gap" question="PV of future net withdrawals on the TIPS real zero curve, funding ratio for $1m, and sensitivities to mortality, pension and rates." cls="model_generated">
          {lg.data ? <>
            <div className="grid grid-cols-3 gap-2"><Kpi label="liability PV" value={usd(lg.data.pv)} /><Kpi label="duration (years)" value={lg.data.duration.toFixed(1)} />
              <Kpi label="funding ratio of $1m" value={lg.data.funding_ratio_for_1m?.toFixed(2) ?? "–"} /></div>
            <Bars horizontal xTitle="scenario" yTitle="PV ($)" yfmt="$,.0f" x={["base", ...Object.keys(lg.data.sensitivities)]} series={[{ name: "PV", y: [lg.data.pv, ...Object.values(lg.data.sensitivities).map((s: any) => s.pv)] }]} />
            {y?.liability ? <div className="text-[11px] text-muted-foreground">Duration gap vs 10Y Treasury: {y.liability.duration_gap_vs_10y_tsy.toFixed(1)} years · vs 10-year ladder: {y.liability.duration_gap_vs_10y_ladder.toFixed(1)} years.</div> : null}
          </> : null}
        </Viz>
        <Viz id="FI-11" title="Cash-flow matching ladder" question="Cost of real zero-coupon rungs for each year's spending against the budget; unfunded years highlighted." cls="model_generated" definition={ld.data?.note}>
          {ld.data ? <><Bars xTitle="year" yTitle="rung cost ($)" yfmt="$,.0f" x={ld.data.years} series={[{ name: "rung cost", y: ld.data.cost }]}
            colors={ld.data.funded.map((f: boolean) => (f ? "#3987e5" : "#e66767"))} />
            <div className="text-xs">Funded years: {ld.data.funded_years} of {ld.data.years.length}. {ld.data.unfunded_years.length ? "Unfunded: years " + ld.data.unfunded_years.join(", ") : "Fully funded within budget."}</div></> : null}
        </Viz>
      </Grid></Sec>
      <Sec id="credit"><Grid>
        <Viz id="FI-09" title="Credit spread & default stress" question="Moody's Baa−Aaa and Baa−10Y Treasury spreads (public FRED); not imputed as corporate bond total returns." cls="observed"
          definition={cr.data ? cr.data.spreads.terms + ". " + cr.data.spreads.retention : ""}>
          {cr.data ? <Lines xTitle="month" yTitle="spread" yfmt=".1%" lines={[{ name: "Baa − Aaa", x: cr.data.spreads.dates, y: cr.data.spreads.baa_aaa }, { name: "Baa − 10Y", x: cr.data.spreads.dates, y: cr.data.spreads.baa_t10 }]} /> : null}
        </Viz>
        <Viz id="FI-13" title="Stock–bond regime co-loss panel" question="Rolling 60m correlation, conditional downside co-loss frequency, and what it implies for shortfall."
          cls="model_generated" definition={co.data ? co.data.definition + ". " + co.data.caveat : ""}>
          {co.data ? <>
            <Lines xTitle="month" yTitle="value" yfmt=".2f" lines={[{ name: "corr 60m", x: co.data.dates, y: co.data.corr_60m }, { name: "P(bond < 0 | equity worst 20%)", x: co.data.dates, y: co.data.coloss_freq_60m }]} />
            <div className="grid grid-cols-2 gap-2">{Object.entries(co.data.shortfall_consequence).map(([k, v]: any) => <Kpi key={k} label={"60/40 4% 30y success, bootstrap of " + k} value={pct(v.p_success_30y_4pct_6040)} sub={v.n_months + " months"} />)}</div>
          </> : null}
        </Viz>
        <Viz id="FI-14" title="Credit quality / duration surface" question="IG vs HY outcomes by duration and spread sensitivity — requires bond-level WRDS data." cls="unavailable"
          empty={cr.data && !cr.data.surface.bond_level_available ? cr.data.surface.reason + ". " + (cr.data.surface.note ?? "") + " " + cr.data.surface.selection_bias : null}>
          {cr.data?.surface.index_stats?.length ? <DataTable rows={cr.data.surface.index_stats} columns={[{ key: "series", label: "sleeve" }, { key: "source", label: "source" },
            { key: "real_mean", label: "real mean", fmt: (v) => pct(v) }, { key: "real_vol", label: "vol", fmt: (v) => pct(v) }, { key: "worst_12m", label: "worst 12m", fmt: (v) => pct(v) }]} /> : <Empty>No credit sleeves.</Empty>}
        </Viz>
      </Grid></Sec>
      <div className="text-[11px] text-muted-foreground">{bp(0.0001)} = 0.01%. All views derive from the public panel; WRDS observed Treasury returns replace model-generated returns automatically when ingested.</div>
    </div>
  );
}

/** Fixed Income & Credit: curves, rate risk, bond returns, liabilities and credit — one set of curve inputs. */
export function FixedIncome() {
  return (
    <ResearchPage page="fixedIncome" intro="Bonds as the financial centrepiece: curves, key-rate risk, convexity, twists, return decomposition, real liabilities, cash-flow matching, co-loss regimes and the value of each bond instrument across the withdrawal spectrum.">
      <Body />
    </ResearchPage>
  );
}
