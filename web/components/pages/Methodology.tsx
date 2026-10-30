"use client";
import { TracingBeam } from "@/components/ui/tracing-beam";
import { Tex } from "@/components/common/Tex";
import { PageHeader } from "@/components/common/Section";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCatalog } from "@/lib/api/hooks";

function H({ children, id }: { children: React.ReactNode; id: string }) {
  return <h2 id={id} className="mb-2 mt-10 text-lg font-semibold tracking-tight first:mt-0">{children}</h2>;
}
function P({ children }: { children: React.ReactNode }) {
  return <p className="mb-3 text-sm leading-relaxed text-muted-foreground">{children}</p>;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function Methodology() {
  const cat = useCatalog();
  return (
    <div>
      <PageHeader title="Methodology" description="Formulas, data sources, assumptions and limitations. Everything below is implemented in backend/lifecycle/engine and tested in backend/tests." />
      <TracingBeam className="px-4">
        <article className="max-w-3xl">
          <H id="wealth">1. Unified wealth dynamics</H>
          <P>All quantities are real (CPI-deflated) at monthly frequency. Cash flows occur at the start of the month; the portfolio then earns its return net of proportional rebalancing cost κ on one-way turnover.</P>
          <Tex block>{String.raw`W_{t+1}=\left(W_t+Y_t+P_t-C_t\right)\left(1+\mathbf w_t^{\top}\mathbf R_{t+1}\right)-\kappa\lVert \mathbf w_t-\tilde{\mathbf w}_t\rVert_1\left(W_t+Y_t+P_t-C_t\right)`}</Tex>
          <P>Weights are long-only on the simplex; investable wealth cannot be negative. The signed net-flow rate places every investor-month on one axis; contributions are reported as a share of income and withdrawals as a share of initial retirement wealth.</P>
          <Tex block>{String.raw`q_t=\frac{C_t-Y_t-P_t}{W_{\mathrm{ref}}},\qquad q_t<0\ \text{accumulation},\quad q_t>0\ \text{decumulation}`}</Tex>

          <H id="income">2. Labor income and pension</H>
          <P>Cocco–Gomes–Maenhout (2005): a deterministic age profile, a permanent random walk (optionally correlated with equity returns) and a transitory shock, mean-corrected so expected income follows the profile. At retirement income is replaced by a CPI-indexed pension, λ times final permanent income, or a fixed real amount.</P>
          <Tex block>{String.raw`\ln Y_t=f(\mathrm{age}_t)+v_t+\varepsilon_t,\qquad v_t=v_{t-1}+u_t,\qquad \operatorname{corr}(u_t,r^e_t)=\rho_{Y,e}`}</Tex>

          <H id="utility">3. Preferences, CE and standard errors</H>
          <Tex block>{String.raw`\max_\pi\ \mathbb E\Big[\sum_t \beta^t S_t\,u(C_t)+\eta\sum_t\beta^{t+1}S_t(1-s_{t+1})\,b(W_{t+1})\Big],\quad u(C)=\frac{C^{1-\gamma}}{1-\gamma},\ \ b(W)=\frac{(W+\underline k)^{1-\gamma}}{1-\gamma}`}</Tex>
          <P>Survival S_t comes from the SSA period life table (a Gompertz fit is used, and flagged, if the table is unavailable). Consumption has a hard floor C_min; when a path cannot fund it, consumption is set to C_min, the gap is booked to an explicit shortfall variable and the path is flagged infeasible.</P>
          <Tex block>{String.raw`\mathrm{CE}(\pi)=\left[\frac{(1-\gamma)\hat U(\pi)}{\sum_t\beta^tS_t}\right]^{\frac1{1-\gamma}},\qquad \Delta_{\mathrm{CE}}=\frac{\mathrm{CE}(\pi^*)}{\mathrm{CE}(\pi_{\mathrm{bench}})}-1`}</Tex>
          <Tex block>{String.raw`\operatorname{SE}[\widehat{\mathrm{CE}}]\approx\Big|\frac{\partial\mathrm{CE}}{\partial U}\Big|\frac{\hat\sigma_U}{\sqrt N},\qquad \frac{\partial \mathrm{CE}}{\partial U}=\frac{\mathrm{CE}}{(1-\gamma)U}`}</Tex>
          <P>Every policy in a comparison is evaluated on identical scenario paths, income draws and survival weights, so the SE of ΔCE is computed from paired path utilities (delta method on the joint mean).</P>

          <H id="shortfall">4. Spending shortfall</H>
          <Tex block>{String.raw`L_j=\sum_{t}\frac{\left(C_{j,t}-F_{j,t}\right)_+}{C_{j,t}},\qquad \mathrm{CVaR}_{95\%}(L)=\mathbb E\left[L\mid L\ge \mathrm{VaR}_{95\%}\right]`}</Tex>
          <P>Spending rules: fixed real (r × W_R indexed to CPI), fixed percentage (reset annually), Guyton–Klinger guardrails (±10% when the current rate leaves [0.8r, 1.2r]), the liability-matched bucket (k years of withdrawals in a TIPS/Treasury ladder) and a utility-optimal amortised rule whose real rate is fitted.</P>

          <H id="dp">5. Dynamic programming and parametric policies</H>
          <Tex block>{String.raw`V_t(x,s)=\max_{c,\mathbf w}\ u(c)+\beta s_{t+1}\,\mathbb E\big[G_{t+1}^{1-\gamma}V_{t+1}(x',s')\big]+\beta\eta(1-s_{t+1})\,\mathbb E[b(aR_{\mathbf w})],\quad x'=\frac{(x-c)R_{\mathbf w}}{G_{t+1}}+y_{t+1}`}</Tex>
          <P>The reduced problem (US equity, 10Y Treasury, T-bills × Markov regimes) is solved by backward induction on a 200-point log grid in normalised cash-on-hand, a 21-point simplex for weights and golden-section refinement of consumption; expectations use Markov-chain nodes per starting regime. The solver recovers the Merton weight (μ−r)/(γσ²) in the i.i.d. two-asset limit (unit-tested). Parametric policies set the growth share</P>
          <Tex block>{String.raw`\alpha_t=\operatorname{clip}\Big(\theta_0+\theta_1\tfrac{\mathrm{age}_t-65}{10}+\theta_2(\ln x_t-\ln 25)+\theta_3\,\mathbb 1\{\hat s_t>0\},\,0,\,1\Big)`}</Tex>
          <P>with θ fitted on seed-set A and reported on an independent seed-set B; the train–test CE gap is reported as over-fitting to simulated noise.</P>

          <H id="scenarios">6. Scenario generators</H>
          <Table>
            <TableHeader><TableRow><TableHead>Generator</TableHead><TableHead>Specification</TableHead><TableHead>Known weakness</TableHead></TableRow></TableHeader>
            <TableBody>
              <TableRow><TableCell>Historical cohorts</TableCell><TableCell>Rolling start months on the joint history</TableCell><TableCell>Few independent long windows</TableCell></TableRow>
              <TableRow><TableCell>Stationary block bootstrap</TableCell><TableCell>Politis–Romano; mean block length by Politis–White</TableCell><TableCell>Cannot produce unseen states</TableCell></TableRow>
              <TableRow><TableCell>Multivariate Student-t</TableCell><TableCell>ν by ML, Ledoit–Wolf-shrunk scatter</TableCell><TableCell>No regime persistence</TableCell></TableRow>
              <TableRow><TableCell>Markov switching</TableCell><TableCell>Gaussian HMM, EM with Hamilton filter + Kim smoother, K by BIC</TableCell><TableCell>Estimation risk on Σ_s</TableCell></TableRow>
              <TableRow><TableCell>Yield-curve factors</TableCell><TableCell>VAR(1) on level/slope/curvature + inflation + other assets; bonds repriced from the curve</TableCell><TableCell>Zero-to-par approximation</TableCell></TableRow>
            </TableBody>
          </Table>
          <P>All generators draw equities, bonds and inflation jointly and produce the same tensor (paths × months × series). Chunks of 2,000 paths use SeedSequence.spawn so results do not depend on worker count.</P>

          <H id="fi">7. Fixed income</H>
          <Tex block>{String.raw`\frac{\Delta P}{P}\approx -D_{\mathrm{mod}}\Delta y+\tfrac12 C(\Delta y)^2,\qquad r\approx \underbrace{y_0\Delta t}_{\text{carry}}+\text{roll-down}-D\,\Delta y+\tfrac12 C\,\Delta y^2`}</Tex>
          <P>PCA is run on monthly changes of GSW zero yields (1–30Y); loadings are checked before being labelled level, slope and curvature. Liabilities are valued on the GSW TIPS real curve.</P>

          <H id="data">8. Data</H>
          <P>Investable returns come from WRDS (CRSP index and Treasury files, Bond Returns, ETFs by PERMNO resolved by ticker and date range) when ingested; until then, public sources are used and model-generated returns are flagged: French library market/RF and international portfolios, and par-bond returns repriced from FRED constant-maturity yields. Yields are never used as returns; missing months are dropped and recorded, never filled.</P>
          {cat.data ? (
            <Table>
              <TableHeader><TableRow><TableHead>Series</TableHead><TableHead>Source</TableHead><TableHead>Provenance</TableHead><TableHead>Coverage</TableHead><TableHead>Licence</TableHead></TableRow></TableHeader>
              <TableBody>
                {cat.data.series.filter((s: any) => !s.series_id.startsWith("gsw_")).map((s: any) => (
                  <TableRow key={s.series_id + s.source}><TableCell>{s.label}</TableCell><TableCell className="font-mono text-[11px]">{s.source}</TableCell>
                    <TableCell>{s.provenance}</TableCell><TableCell className="tabular-nums">{s.first_obs} → {s.last_obs}</TableCell><TableCell>{s.licence_class}</TableCell></TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}

          <H id="limits">9. Limitations</H>
          <P>Simulated precision is not model correctness: a result is called robust only if the sign of ΔCE survives Monte Carlo error, parameter re-estimation and model disagreement. Overlapping historical cohorts are not independent. The DP is solved at annual frequency on a reduced universe, and its gains are in-model. Regime labels are descriptive and filtered probabilities alone drive decisions. The engine is pre-tax and long-only; outputs are research, not investment advice.</P>

          <H id="refs">References</H>
          <ul className="mb-10 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            <li>Cocco, Gomes &amp; Maenhout (2005), Consumption and Portfolio Choice over the Life Cycle, RFS 18(2).</li>
            <li>Merton (1969), Lifetime Portfolio Selection under Uncertainty, REStat 51(3).</li>
            <li>Hamilton (1989), Econometrica 57(2); Engle (2002), JBES 20(3).</li>
            <li>Politis &amp; Romano (1994), JASA 89(428); Politis &amp; White (2004), Econometric Reviews 23(1).</li>
            <li>Gürkaynak, Sack &amp; Wright (2007, 2010); Adrian, Crump &amp; Moench (2013).</li>
            <li>Rockafellar &amp; Uryasev (2000); Ledoit &amp; Wolf (2004); Bengen (1994); Guyton &amp; Klinger (2006); Fama &amp; French (1993).</li>
          </ul>
        </article>
      </TracingBeam>
    </div>
  );
}
