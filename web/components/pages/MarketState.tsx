"use client";
import { useState } from "react";
import { toast } from "sonner";
import { ResearchPage, Sec } from "@/components/research/page";
import { useResearchContext } from "@/lib/store";
import { DataTable, Empty, Grid, Kpi, Seg, StudyGate, Viz, Warnings } from "@/components/research/kit";
import { Fan, Heat, Lines, pct, usd } from "@/components/visualizations/charts";
import { apiPost } from "@/lib/api/client";
import { useV2 } from "@/lib/api/v2";

/* eslint-disable @typescript-eslint/no-explicit-any */
function Ribbon() {
  const rb = useV2("/v1/market-state/ribbon", undefined, { refetch: 30_000 });
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setBusy(true);
    try {
      const r = await apiPost<any>("/v1/data/refresh?group=treasury_daily", {});
      toast.success("Backend refresh " + r.status + " (Treasury daily curves). Check the Refresh audit panel.");
    } catch (e) { toast.error(String((e as Error).message)); } finally { setBusy(false); }
  }
  return (
    <Viz id="MS-01" title="As-of market state ribbon" question={"Latest observation per source vs today (" + (rb.data?.today ?? "…") + "); stale and licence flags."} cls="observed"
      definition={rb.data?.note}>
      <div className="mb-2 flex justify-end"><button disabled={busy} onClick={refresh} className="rounded border border-border px-2 py-1 text-xs hover:bg-muted">Update (backend job)</button></div>
      {rb.data ? <div className="grid gap-2 md:grid-cols-4">
        {rb.data.sources.map((s: any) => (
          <div key={s.source} className="rounded-lg border border-border p-2 text-xs">
            <div className="flex items-center justify-between"><span className="font-medium">{s.label}</span>
              <span className={"rounded px-1 text-[10px] " + (s.status === "not ingested" ? "bg-muted text-muted-foreground" : s.stale ? "bg-[var(--viz-s4)]/20" : "bg-[var(--viz-s3)]/20")}>
                {s.status === "not ingested" ? "not ingested" : s.stale ? "▲ stale" : "● current"}</span></div>
            <div className="mt-1 text-muted-foreground">obs {s.latest_observation ?? "–"} · retrieved {s.retrieved_vintage ?? "–"}</div>
            <div className="text-muted-foreground">{s.days_since_observation !== undefined ? s.days_since_observation + " days old · " : ""}{s.licence}</div>
            {s.note ? <div className="mt-1 text-[10px] text-muted-foreground">{s.note}</div> : null}
          </div>))}
      </div> : null}
    </Viz>
  );
}

function PitSelector() {
  const [sid, setSid] = useState("cpi_nsa");
  const [asof, setAsof] = useState("2008-10-10");
  const q = useV2("/v1/market-state/pit", { series_id: sid, as_of: asof });
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded border border-border p-2 text-xs">
      <span className="text-muted-foreground">Historical PIT selector:</span>
      <select value={sid} onChange={(e) => setSid(e.target.value)} className="h-7 rounded border border-input bg-transparent px-1">
        {["cpi_nsa", "s_unrate", "s_indpro", "y_dgs10", "s_acm_tp10"].map((s) => <option key={s}>{s}</option>)}</select>
      <input type="date" value={asof} onChange={(e) => setAsof(e.target.value)} className="h-7 rounded border border-input bg-transparent px-1" />
      {q.data ? (q.data.status === "UnavailableAsOf" ? <span>UnavailableAsOf</span> :
        <span>latest known: period {q.data.observation_period} (published {q.data.available_from}) = {q.data.value.toFixed(5)}</span>) : null}
    </div>
  );
}

/** Last calendar day of a YYYY-MM month ("" stays ""), used as the study's calibration end. */
function monthEnd(m: string): string {
  if (!m) return "";
  const [y, mo] = m.split("-").map(Number);
  return m + "-" + String(new Date(y, mo, 0).getDate()).padStart(2, "0");
}

function Body() {
  const setCtx = useResearchContext((c) => c.set);
  const [asOf, setAsOf] = useState<string>(useResearchContext.getState().asOf.slice(0, 7));
  const v = useV2(asOf ? "/v1/market-state/" + asOf : "/v1/market-state/latest");
  const audit = useV2("/v1/market-state/audit");
  const [curveBasis, setCurveBasis] = useState<"zero" | "par">("zero");
  const d = v.data;
  return (
    <div className="space-y-4">
      <Sec id="snapshot"><Ribbon /></Sec>
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card px-3 py-2 text-xs">
        <label className="flex flex-col gap-1"><span className="text-muted-foreground">as-of (historical replay; blank = latest)</span>
          <input type="month" value={asOf} onChange={(e) => { setAsOf(e.target.value); setCtx({ asOf: monthEnd(e.target.value) }); }} className="h-8 rounded border border-input bg-transparent px-2" /></label>
        <span className="text-muted-foreground">{d ? "as of " + d.as_of + " — " + d.as_of_rule : "loading…"}. Changing the as-of date never revises stored runs.</span>
      </div>
      {!d ? <div className="h-96 animate-pulse rounded-xl bg-muted/40" /> : <>
      <Sec id="snapshot"><Grid>
        <Viz id="MS-02" title="Nominal vs real curve" question="Curve state at the as-of date; zero/par selection with provenance." cls="model_generated" definition={d.curves.nominal?.basis + "; " + (d.curves.real?.basis ?? "no real curve at this date")}>
          <Seg label="basis" value={curveBasis} onChange={setCurveBasis} options={[{ value: "zero", label: "zero" }, { value: "par", label: "par" }]} />
          <Lines xTitle="maturity (years)" yTitle="yield" yfmt=".2%" lines={[
            ...(d.curves.nominal ? [{ name: "nominal " + curveBasis + " (" + d.curves.nominal.observation_date + ")", x: d.curves.nominal.maturities, y: d.curves.nominal[curveBasis] }] : []),
            ...(d.curves.real && curveBasis === "zero" ? [{ name: "real zero (" + d.curves.real.observation_date + ")", x: d.curves.real.maturities, y: d.curves.real.zero }] : []),
            ...(d.curves.daily_par?.nominal ? [{ name: "Treasury daily par " + d.curves.daily_par.nominal.observation_date, x: d.curves.daily_par.nominal.tenors, y: d.curves.daily_par.nominal.par_yield, mode: "lines+markers" as const }] : [])]} />
        </Viz>
        <Viz id="MS-03" title="Inflation / term-premium decomposition" question="10Y nominal vs TIPS real yield vs breakeven; ACM term premium and expected short rate as separate model components." cls="observed" definition={d.decomposition.note}>
          <div className="mb-2 grid grid-cols-5 gap-1 text-xs">{[["nominal", "nominal_10y"], ["real", "real_10y"], ["breakeven", "breakeven_10y"], ["ACM TP", "acm_term_premium_10y"], ["ACM E[r]", "acm_expected_short_rate_10y"]]
            .map(([l, k]) => <Kpi key={k} label={l} value={pct(d.decomposition[k], 2)} />)}</div>
          <Lines xTitle="month" yTitle="yield" yfmt=".1%" lines={[["10Y nominal (CMT)", "y_dgs10"], ["10Y TIPS real", "y_dfii10"], ["10Y breakeven", "y_t10yie"], ["ACM term premium", "s_acm_tp10"], ["ACM expected short rate", "s_acm_rny10"]]
            .map(([n, k]) => ({ name: n, x: d.series[k].dates, y: d.series[k].values, width: 1.5 }))} />
        </Viz>
        <Viz id="MS-04" title="Bond valuation dashboard" question="Duration, real yield, curve slopes, roll-down and yield-to-income, with inputs stated." cls="model_generated" definition={d.valuation.assumptions}>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Kpi label="10Y modified duration" value={d.valuation.duration_10y?.toFixed(2) ?? "–"} />
            <Kpi label="10Y real yield" value={pct(d.valuation.real_yield_10y, 2)} />
            <Kpi label="2s10s slope" value={pct(d.valuation.slope_2s10s, 2)} />
            <Kpi label="5s30s slope" value={pct(d.valuation.slope_5s30s, 2)} />
            <Kpi label="1m roll-down (10Y)" value={pct(d.valuation.roll_down_1m_10y, 3)} />
            <Kpi label="income per $1m (10Y par)" value={usd(d.valuation.income_per_1m_10y_par)} sub="nominal, per year" />
            <Kpi label="30y real ladder income per $1m" value={usd(d.valuation.real_income_30y_ladder_per_1m)} sub="real, per year" />
          </div>
        </Viz>
      </Grid></Sec>
      <Sec id="dependence"><Grid>
        <Viz id="MS-05" title="Rolling stock–bond correlation" question="12/36/60-month rolling correlation with Fisher-z 95% bands and DCC-GARCH conditional correlation." cls="model_generated">
          <Warnings items={d.correlation.warnings} />
          <Lines xTitle="month" yTitle="correlation" yfmt=".2f" lines={[["12", "12m"], ["36", "36m"], ["60", "60m"]].map(([k, n]) => ({ name: n, x: d.correlation.dates, y: d.correlation.rolling[k].r,
            lo: k === "36" ? d.correlation.rolling[k].lo : undefined, hi: k === "36" ? d.correlation.rolling[k].hi : undefined, width: 1.5 })).concat([{ name: "DCC", x: d.correlation.dates, y: d.correlation.dcc, width: 1 } as any])} />
        </Viz>
        <Viz id="MS-06" title="Filtered regime probabilities" question="Point-in-time (filtered, not smoothed) Markov-switching probabilities; latest value and model vintage." cls="model_generated" definition={d.regime.note}>
          <div className="mb-2 grid grid-cols-2 gap-2">{d.regime.names.map((n: string, i: number) => <Kpi key={n} label={"P(" + n + ") latest"} value={pct(d.regime.latest[i])} sub={"next month " + pct(d.regime.one_step_ahead[i])} />)}</div>
          <Lines xTitle="month" yTitle="probability" yfmt=".0%" lines={d.regime.names.map((n: string, i: number) => ({ name: n, x: d.regime.dates, y: d.regime.filtered.map((r: number[]) => r[i]), width: 1.2 }))} />
          <div className="text-[11px] text-muted-foreground">vintage: catalog {d.regime.model_vintage.catalog_hash}, window {d.regime.model_vintage.window.join(" → ")}, k = {d.regime.model_vintage.k}</div>
        </Viz>
      </Grid></Sec>
      <Sec id="releases"><Grid>
        <Viz id="MS-08" title="Economic release timeline" question="Observation period, publication lag, availability and vintage of each macro/rate series; revisions noted." cls="observed">
          <DataTable rows={d.releases} columns={[{ key: "series_id", label: "series" }, { key: "last_period", label: "last period" }, { key: "available_from", label: "available from" },
            { key: "publication_lag_days", label: "lag (days)" }, { key: "latest_known_at_as_of", label: "known at as-of" }, { key: "vintage", label: "vintage" }, { key: "revisions", label: "revisions" }]} />
          <PitSelector />
        </Viz>
        <Viz id="MS-09" title="Credit spread and liquidity conditions" question="Moody's Baa−Aaa and Baa−10Y spreads to the as-of date." cls="observed" definition={d.credit.source + " · " + d.credit.licence}>
          <Lines xTitle="month" yTitle="spread" yfmt=".1%" lines={[{ name: "Baa − Aaa", x: d.credit.dates, y: d.credit.baa_aaa }, { name: "Baa − 10Y", x: d.credit.dates, y: d.credit.baa_t10 }]} />
        </Viz>
        <Viz id="MS-11" title="Recent ETF proxy panel (optional)" question="WRDS daily/monthly adjusted returns for permitted ETF proxies." cls="observed" empty={d.etf_proxies.available ? null : d.etf_proxies.reason}>
          <DataTable rows={d.etf_proxies.series} columns={[{ key: "series_id", label: "series" }, { key: "source", label: "source" }, { key: "last_obs", label: "last obs" }]} />
        </Viz>
        <Viz id="MS-12" title="Refresh audit" question="Ingestion runs, daily-store refresh attempts and failures, source choices, gaps and vintages." cls="observed">
          {audit.data ? <>
            <DataTable rows={[...audit.data.ingest_runs.map((r: any) => ({ when: r.at, what: "panel build (" + (r.offline ? "offline snapshot" : "live") + (r.wrds ? " + WRDS" : "") + ")", detail: r.catalog_hash })),
              ...audit.data.daily_store.flatMap((dd: any) => (dd.attempts ?? []).map((a: any) => ({ when: dd.retrieved_at, what: "treasury " + a.kind + " " + a.year, detail: a.status + (a.error ? ": " + a.error : "") })))]}
              columns={[{ key: "when", label: "when" }, { key: "what", label: "what" }, { key: "detail", label: "status / detail" }]} />
            <div className="mt-2 text-[11px] text-muted-foreground">Vintages: {audit.data.vintages.join(", ")} · series with gaps: {audit.data.invalid_series.map((s: any) => s.series_id).join(", ") || "none"}</div>
          </> : null}
        </Viz>
      </Grid></Sec>
      </>}
      <Sec id="conditional"><StudyGate kind="asof" title="As-of conditional scenario study" description="Markov-switching paths started from the filtered state at the as-of date vs the stationary start, same calibration and seeds.">
        {(env) => {
          const r = env.results;
          return (
            <Grid>
              <Viz id="MS-07" title="Current-condition scenario fan" question={"60/40 real wealth: conditional on the filtered state at " + r.as_of + " vs unconditional (stationary start)."} runId={env.run_id} cls="model_generated"
                definition={"Start probabilities — conditional: " + r.start_probabilities.conditional.map((p: number) => pct(p)).join(" / ") + "; unconditional: " + r.start_probabilities.unconditional.map((p: number) => pct(p)).join(" / ") + " (" + r.regime_names.join(" / ") + "). Distributions, not point forecasts."}>
                <Fan x={r.fans.conditional.wealth.p50.map((_: number, i: number) => i)} q={r.fans.conditional.wealth} name="conditional" compare={{ q: r.fans.unconditional.wealth, name: "unconditional" }}
                  xTitle="years ahead" yTitle="real wealth (4% draw)" />
                <div className="grid grid-cols-2 gap-2">{(["conditional", "unconditional"] as const).map((k) => <Kpi key={k} label={k + " P(30y success)"} value={pct(r.fans[k].success.p)} ci={"95% CI " + pct(r.fans[k].success.lo) + "–" + pct(r.fans[k].success.hi)} />)}</div>
              </Viz>
              <Viz id="MS-10" title="Scenario delta board" question="Change in survival over withdrawal × bond share when starting from the observed state; × = within 2 MC SE." runId={env.run_id} cls="model_generated" definition={r.model_uncertainty_note}>
                <Heat x={r.r} y={r.b} z={r.delta_surface} diverging xTitle="withdrawal rate" yTitle="bond share" zTitle="Δ P(success)" zfmt="+.1%" xfmt={(x) => pct(x, 1)} yfmt={(x) => pct(x, 0)}
                  mask={r.delta_flag.map((row: number[]) => row.map((f) => f === 0))} />
                <DataTable rows={r.thresholds.conditional.map((t: any, i: number) => ({ r: t.r, cond: t.b_min, unc: r.thresholds.unconditional[i].b_min, sc: t.status, su: r.thresholds.unconditional[i].status }))}
                  columns={[{ key: "r", label: "r", fmt: (x) => pct(x, 1) }, { key: "cond", label: "b_min conditional", fmt: (x) => (x === null ? "none" : pct(x, 0)) }, { key: "unc", label: "b_min unconditional", fmt: (x) => (x === null ? "none" : pct(x, 0)) }]} />
              </Viz>
            </Grid>
          );
        }}
      </StudyGate></Sec>
      {d ? null : <Empty>Loading market state…</Empty>}
    </div>
  );
}

/** Market State: latest public observations with their dates, dependence, releases and as-of conditional scenarios. */
export function MarketState() {
  return (
    <ResearchPage page="marketState" intro="Latest available public rates and macro observations with observation, publication and retrieval dates kept separate — not a live ticker. Historical as-of replay respects publication lags; conditional scenarios are pinned to their as-of date and calibration.">
      <Body />
    </ResearchPage>
  );
}
