"use client";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { ResearchPage, Sec } from "@/components/research/page";
import { MathematicalNotes } from "@/components/research/methodology/MathematicalNotes";
import { VisualizationReference } from "@/components/research/methodology/VisualizationReference";
import { Tex } from "@/components/common/Tex";
import { DataTable, Seg, Viz } from "@/components/research/kit";
import { useCatalog } from "@/lib/api/hooks";
import { useV2 } from "@/lib/api/v2";

/* eslint-disable @typescript-eslint/no-explicit-any */
const STEPS = [
  ["Public + WRDS data", "FRED/ALFRED, Treasury, Fed GSW, NY Fed ACM, French, SSA; WRDS CRSP/Bond Returns (server-side)"],
  ["Canonical panel", "one source per series, provenance, publication lags, content hashes, catalog hash"],
  ["Scenarios", "cohorts, block bootstrap, Student-t, Markov switching, curve-factor VAR; PIT decision signal"],
  ["Investor cash flows", "income, pension, mortality, signed planned q, desired vs funded spending"],
  ["Allocation · spending · trading", "target weights | spending rule | trading policy (holdings ledger, costs)"],
  ["Utilities & metrics", "CE of funded consumption, fixed-horizon & until-death success, shortfall severity"],
  ["Inference", "paired ΔCE, Wilson CIs, joint bootstrap of b_min, Holm/BH, walk-forward OOS"],
  ["Figures & reports", "F1–F6, run-ID provenance, derived exports, paper"],
];

function Pipeline() {
  const w = 1100, bh = 64, gap = 18, bw = (w - gap * (STEPS.length - 1)) / STEPS.length;
  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${w} 150`} className="min-w-[900px]" role="img" aria-label="Research pipeline from data to figures">
        <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="var(--viz-text-2)" /></marker></defs>
        {STEPS.map(([title, sub], i) => {
          const x = i * (bw + gap);
          return (
            <g key={title}>
              <rect x={x} y={20} width={bw} height={bh} rx={8} fill="var(--viz-surface)" stroke="var(--viz-s1)" strokeWidth={1.5} />
              <text x={x + bw / 2} y={48} textAnchor="middle" fontSize={11} fontWeight={600} fill="var(--viz-text)">{title}</text>
              <foreignObject x={x} y={90} width={bw} height={60}><div style={{ fontSize: 9, color: "var(--viz-text-2)", textAlign: "center", lineHeight: 1.25 }}>{sub}</div></foreignObject>
              {i < STEPS.length - 1 ? <line x1={x + bw} y1={52} x2={x + bw + gap - 2} y2={52} stroke="var(--viz-text-2)" strokeWidth={1.5} markerEnd="url(#arr)" /> : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

const EQ: Record<string, { tex: string[]; text: string }> = {
  wealth: { text: "Holdings ledger at month t: flows first, then the trading decision, then next-month returns. Unfunded spending is booked, never consumed.", tex: [
    String.raw`D^{\text{funded}}_t=\min(D^{\text{desired}}_t,\,W_t),\qquad U_t=D^{\text{desired}}_t-D^{\text{funded}}_t\ \ge 0`,
    String.raw`h^{+}_{i,t}=h_{i,t}-s_{i,t}+c_{i,t}+\Delta h_{i,t},\qquad \tau_t=\sum_i |\Delta h_{i,t}|(f_i+\tfrac12 s_i)+\lambda_i\frac{\Delta h_{i,t}^2}{\$1\text{m}}`,
    String.raw`W_{t+1}=\sum_i h^{+}_{i,t}\,(1+R_{i,t+1}),\qquad q_t=\frac{D_t-C^{\text{contrib}}_t}{W_{\text{ref}}}`] },
  utility: { text: "CRRA utility of actually funded consumption, mortality-weighted; the utility floor enters utility only.", tex: [
    String.raw`\mathcal U=\mathbb E\sum_t\beta^tS_t\,u\big(\max(C^{\text{funded}}_t,\underline c)\big),\quad u(c)=\frac{c^{1-\gamma}}{1-\gamma}`,
    String.raw`\mathrm{CE}=\Big[\frac{(1-\gamma)\hat{\mathcal U}}{\sum_t\beta^tS_t}\Big]^{1/(1-\gamma)},\qquad \Delta_{\mathrm{CE}}=\mathrm{CE}_\pi/\mathrm{CE}_b-1`] },
  necessity: { text: "The minimum bond share is solved on the feasible set (possibly empty or disconnected) and re-solved in every bootstrap replicate.", tex: [
    String.raw`\mathcal F(r,T;s^*)=\{b:\ \hat P_{\text{succ}}(b,r,T)\ge s^*\},\qquad b_{\min}=\inf\mathcal F\ \ (\text{or 'no feasible allocation'})`,
    String.raw`\hat P_{\text{succ}}=\frac1N\sum_j\mathbf 1\{\tau_j\ge 12T\},\qquad P_{\text{alive}}=1-\mathbb E\big[S(\tau)\mathbf 1\{\tau<\infty\}\big]`] },
  ci: { text: "Monte Carlo CIs are conditional on the fitted model; parameter and model uncertainty are reported separately.", tex: [
    String.raw`\text{Wilson: }\ \frac{\hat p+\frac{z^2}{2N}\pm z\sqrt{\frac{\hat p(1-\hat p)}{N}+\frac{z^2}{4N^2}}}{1+z^2/N}`,
    String.raw`\operatorname{SE}(\Delta_{\mathrm{CE}})^2\approx \nabla g^{\top}\,\widehat{\operatorname{Cov}}(U_\pi,U_b)\,\nabla g/N\quad(\text{paired paths})`] },
  duration: { text: "Full repricing on the GSW zero curve; Taylor approximation and key-rate buckets for diagnostics.", tex: [
    String.raw`P=\sum_k c_k e^{-z(t_k)t_k},\quad D_{\text{mod}}=-\frac1P\frac{\partial P}{\partial y},\quad \text{DV01}=\frac{D_{\text{mod}}P}{10^4}`,
    String.raw`\frac{\Delta P}{P}\approx -D_{\text{mod}}\Delta y+\tfrac12 \mathcal C\,\Delta y^2,\qquad \sum_k \mathrm{KRD}_k=D_{\text{eff}}`] },
  rebalancing: { text: "Triggers are evaluated on post-flow, pre-trade weights at monitoring dates; Browne 15/35 checks once a year and restores all sleeves.", tex: [
    String.raw`\text{band: }\ \max_i|w_{i,t}-w^*_{i}|>\delta,\qquad \text{Browne: } t\bmod 12=0\ \wedge\ \exists i: w_{i,t}\notin[0.15,0.35]`,
    String.raw`\text{utility rule: trade iff }\ \tfrac12\gamma\,(w-w^*)^{\top}\Sigma(w-w^*)\cdot 12\cdot W_t>\hat\tau_t`] },
  posterior: { text: "Hamilton filter on each simulated path: decisions at t use the predicted probability from information through t−1.", tex: [
    String.raw`\xi_{t|t}\propto \xi_{t|t-1}\odot f(x_t\mid s_t),\qquad \xi_{t+1|t}=P^{\top}\xi_{t|t}`,
    String.raw`\hat s^{\text{decision}}_t=\arg\max_k\ \xi_{t|t-1}(k)\quad(\text{oracle } s_t \text{ shown only as a non-tradable bound})`] },
};

const REFS = [
  ["Bengen (1994) Determining Withdrawal Rates Using Historical Data", "https://www.financialplanningassociation.org/sites/default/files/2021-04/MAR04%20Determining%20Withdrawal%20Rates%20Using%20Historical%20Data.pdf"],
  ["Guyton & Klinger (2006) Decision Rules and Maximum Initial Withdrawal Rates", "https://www.financialplanningassociation.org/article/journal/MAR06-decision-rules-and-maximum-initial-withdrawal-rates"],
  ["Cocco, Gomes & Maenhout (2005) Consumption and Portfolio Choice over the Life Cycle", "https://doi.org/10.1093/rfs/hhi017"],
  ["Merton (1969) Lifetime Portfolio Selection Under Uncertainty", "https://doi.org/10.2307/1926560"],
  ["Hamilton (1989) Markov switching", "https://doi.org/10.2307/1912559"],
  ["Engle (2002) Dynamic Conditional Correlation", "https://doi.org/10.1198/073500102288618487"],
  ["Ledoit & Wolf (2004) Well-conditioned covariance estimator", "https://doi.org/10.1016/S0047-259X(03)00096-4"],
  ["Politis & White (2004) Automatic block-length selection", "https://www.math.ucsd.edu/~politis/SBblock-revER.pdf"],
  ["FRED / ALFRED real-time semantics", "https://fred.stlouisfed.org/docs/api/fred/realtime_period.html"],
  ["US Treasury interest-rate statistics", "https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics"],
  ["World Gold Council price data and LBMA licensing caveat", "https://www.gold.org/goldhub/data/gold-prices"],
];

const LIMITS = [
  ["Bond returns in public mode are model_generated", "Par bonds repriced from CMT yields; not observed total-return indices. Interpretation of duration-specific results is conditional until WRDS CRSP Treasury returns are ingested."],
  ["No observed gold series without WRDS", "Classic Permanent Portfolio results with gold are not computed in public mode; only gold-free ablations run. Do not interpret ex-gold results as PP results."],
  ["Macro vintages", "ALFRED real-time vintages are not ingested; revised series (INDPRO, UNRATE, CPI-SA) are used descriptively, never as tradable signals."],
  ["Overlapping historical cohorts", "Cohort results are not independent trials; no binomial CIs are reported for them."],
  ["Monte Carlo CIs are model-conditional", "They do not include parameter or model uncertainty, which are reported separately (refits, generator disagreement)."],
  ["No taxes, no tax lots", "All cost and rebalancing results are pre-tax; no 'after-tax alpha' is claimed."],
  ["US-centric assets and inflation; SSA period life table", "Results do not transfer to other currencies or cohort-specific mortality without re-estimation."],
  ["Interpretation prohibited", "Synthetic-fixture runs, oracle-regime policies and diagnostic-grade (pilot) runs must not be cited as findings. Nothing here is personalised advice."],
];

function Body() {
  const cat = useCatalog();
  const as = useV2("/v1/methodology/assumptions");
  const bib = useV2("/v1/methodology/bibliography");
  const studies = useV2("/v1/studies");
  const health = useV2<any>("/health");
  const topic = useSearchParams().get("topic");
  const [eq, setEq] = useState(topic && topic in EQ ? topic : "wealth");
  const [study, setStudy] = useState("frontier");
  const spec = studies.data?.studies.find((s: any) => s.kind === study)?.default_spec;
  return (
    <div className="space-y-4">
      <Sec id="pipeline">
      <Viz id="MT-01" title="Pipeline diagram" question="data → canonical panel → scenarios → investor cash flows → allocation / spending / trading → utilities → inference → figures" cls="observed"><Pipeline /></Viz>
      <Viz id="MT-02" title="Equation explorer" question="The equations the engine implements, by topic." cls="observed">
        <Seg value={eq} onChange={setEq} options={Object.keys(EQ).map((k) => ({ value: k, label: k }))} />
        <p className="mt-2 text-xs text-muted-foreground">{EQ[eq].text}</p>
        {EQ[eq].tex.map((t) => <Tex key={t} block>{t}</Tex>)}
      </Viz>
      </Sec>
      <Sec id="data">
        <Viz id="MT-03" title="Data dictionary" question="Canonical ID, quantity, coverage, source, vintage, transformation (provenance) and licence of every series." cls="observed">
          <div className="max-h-96 overflow-auto"><DataTable rows={cat.data?.series ?? []} columns={[{ key: "series_id", label: "canonical ID" }, { key: "label", label: "label" }, { key: "quantity", label: "quantity" },
            { key: "units", label: "units" }, { key: "first_obs", label: "first" }, { key: "last_obs", label: "last" }, { key: "source", label: "source" }, { key: "vintage", label: "vintage" },
            { key: "provenance", label: "transformation" }, { key: "licence_class", label: "licence" }]} /></div>
        </Viz>
        <Viz id="MT-04" title="Assumption registry" question="Every default and documented decision, with where its sensitivity is studied." cls="observed">
          <DataTable rows={as.data?.decisions ?? []} columns={[{ key: "decision", label: "decision" }, { key: "value", label: "choice" }, { key: "sensitivity", label: "sensitivity" }]} />
          <details className="mt-2 text-xs"><summary className="cursor-pointer text-muted-foreground">all study defaults ({as.data?.defaults.length ?? 0})</summary>
            <div className="max-h-72 overflow-auto"><DataTable rows={as.data?.defaults ?? []} columns={[{ key: "study", label: "study" }, { key: "parameter", label: "parameter" }, { key: "default", label: "default", fmt: (v) => JSON.stringify(v) }]} /></div></details>
        </Viz>
      </Sec>
      <Sec id="references">
        <Viz id="MT-05" title="Research bibliography" question="References in paper/references.bib plus the methodological and data sources this build relies on (including caveats and contradictory evidence)." cls="observed">
          <DataTable rows={bib.data?.entries ?? []} columns={[{ key: "key", label: "key" }, { key: "author", label: "author" }, { key: "year", label: "year" }, { key: "title", label: "title" },
            { key: "doi", label: "link", fmt: (v, r) => (v ? <a className="underline" href={"https://doi.org/" + v}>doi</a> : r.url ? <a className="underline" href={r.url}>url</a> : "–") }]} />
          <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs">{REFS.map(([t, u]) => <li key={t}><a className="underline" href={u} target="_blank" rel="noreferrer">{t}</a></li>)}</ul>
        </Viz>
      </Sec>
      <Sec id="limitations">
        <Viz id="MT-06" title="Validation & model limitations" question="Unresolved issues and cases where interpretation is prohibited." cls="observed">
          <DataTable rows={LIMITS.map(([a, b]) => ({ a, b }))} columns={[{ key: "a", label: "limitation" }, { key: "b", label: "consequence" }]} />
        </Viz>
      </Sec>
      <Sec id="reproduce">
      <Viz id="MT-07" title="Reproducible methods" question="CLI and API recipes, example study specs and the method version." cls="observed"
        definition={"engine " + (health.data?.engine_version ?? "") + " · semantic version " + (health.data?.semantic_version ?? "")}>
        <div className="grid gap-3 lg:grid-cols-2">
          <pre className="overflow-auto rounded border border-border p-3 text-[11px]">{`# public-only demo, from a clean clone
make setup && make data-offline
python -m lifecycle.cli seed-v2            # F1–F6 default studies
python -m lifecycle.cli seed-v2 --only frontier
python -m lifecycle.cli reproduce <run_id> # asserts identical summaries
python -m lifecycle.cli selftest           # pytest + recorded result
python -m lifecycle.cli market-refresh     # Treasury daily curves (network)
python -m lifecycle.cli entitlements       # WRDS scan (authorised host)

# API (idempotent by spec hash)
curl -X POST localhost:8000/v1/studies/frontier -H 'content-type: application/json' -d '{}'
curl 'localhost:8000/v1/studies/frontier/latest'
curl 'localhost:8000/v1/studies/run/<id>/export?format=csv'`}</pre>
          <div>
            <Seg value={study} onChange={setStudy} options={(studies.data?.studies ?? []).map((s: any) => ({ value: s.kind, label: s.kind }))} />
            <pre className="mt-2 max-h-80 overflow-auto rounded border border-border p-3 text-[10px]">{JSON.stringify(spec ?? {}, null, 2)}</pre>
          </div>
        </div>
      </Viz>
      </Sec>
      <Sec id="mathematics"><MathematicalNotes /></Sec>
      <Sec id="visualizations"><VisualizationReference /></Sec>
    </div>
  );
}

/** Methodology & Data: pipeline, mathematics, data dictionary, references, limitations, reproduction, visualization reference. */
export function Methodology() {
  return (
    <ResearchPage page="methodology" intro="How every number is produced: pipeline, equations, the full mathematical notes, data dictionary and licences, assumptions, references, limitations, reproduction recipes and the reference entry for every visualization.">
      <Body />
    </ResearchPage>
  );
}
