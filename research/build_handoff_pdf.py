"""Create the formal report and one-page executive brief from verified aggregate evidence."""
from pathlib import Path
from xml.sax.saxutils import escape
import json

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'research/integrated_handoff_2026_11_20'
PDF=ROOT.parent/'output/pdf'
PDF.mkdir(exist_ok=True,parents=True)
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='ReportBody',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=9))
styles.add(ParagraphStyle(name='ReportSmall',fontName='Helvetica',fontSize=8,leading=10.5,spaceAfter=6))
styles.add(ParagraphStyle(name='ReportTitle',fontName='Helvetica-Bold',fontSize=23,leading=28,textColor=colors.HexColor('#173b4c'),spaceAfter=12))
styles.add(ParagraphStyle(name='ReportSubtitle',fontSize=11,leading=14,textColor=colors.HexColor('#48616c'),spaceAfter=13))


def p(text,small=False):return Paragraph(text,styles['ReportSmall' if small else 'ReportBody'])
def heading(text):return Paragraph(text,styles['Heading2'])
def figure(name,width=7.05):
    from PIL import Image as PILImage
    path=HERE/'figures'/f'{name}.png'
    with PILImage.open(path) as im:w,h=im.size
    return Image(str(path),width=width*inch,height=width*inch*h/w)


def footer(canvas,doc):
    canvas.setStrokeColor(colors.HexColor('#d0dce1'));canvas.line(45,39,567,39)
    canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#48616c'))
    canvas.drawString(45,26,'Fixed Income research | November 20, 2026 | Aggregate evidence only')
    canvas.drawRightString(567,26,str(doc.page))


def write(name,story):
    doc=SimpleDocTemplate(str(PDF/name),pagesize=(612,792),rightMargin=45,leftMargin=45,topMargin=42,bottomMargin=49,
        title='Age, willingness and liquid-budget resilience',author='Fixed Income project')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)


brief=[
('Question and data','We tested how age relates to reported financial-risk willingness and liquid resources available to fund household outlays. The US study uses the 2016, 2019, 2022 and 2025 Survey of Consumer Finances, five imputations and 999 official replicate weights. Independent evidence includes Italian SHIW and Indian SEBI microdata, with a 13-country inventory distinguishing microdata, aggregates and literature.'),
('Age is predictive','Age improves held-out predictions of both willingness and accessible-resource coverage in 2019, 2022 and 2025. Adding age to income/wealth improves 2025 Brier loss by 0.01076 for willingness and 0.00445 for coverage. All six incremental-age tests survive Holm adjustment. Intervals condition on the fitted training models.'),
('The capacity result depends on the shock','Older US households report lower willingness; the 2025 demographic-adjusted age-75-minus-30 contrast is -20.59 percentage points. Raw liquidity coverage rises with age, but the cash-coverage contrast becomes -3.22 points (-7.35 to +0.90) after income/wealth adjustment. Under a market loss plus six months without earned income, the adjusted resilience contrast is +16.51 points. Adding earned-income share reduces it to +0.37 points (-6.43 to +7.17). Continuing pensions, rather than a general age advantage, is central to that scenario.'),
('Resources and willingness','In 2025, meeting the three-month cash threshold is associated with +7.35 points of willingness after age, demographic and financial adjustment. The earned-income-interruption threshold gives +1.66 points, with an interval crossing zero. In independent SHED panel evidence, a baseline emergency fund predicts 6.72 points fewer unpaid bills next year after baseline hardship/stability controls. This supports a hardship-related proxy, not the new stress formula or a causal willingness effect.'),
('Allocation validation','The matched three-asset WRDS age-plus-flow rule gains 0.1041% resources CE versus age-only, with a 95% paired interval of -0.0783% to +0.3289%. A stable improvement is not established. New 16-cell budget scenarios show where reserve constraints matter, but outcomes at mean inputs are not population success estimates or individual investment recommendations.'),
('International and practical conclusion','Italy and India support lower willingness at older ages/cohorts under their stated adjustments. Comparable capacity is not identified for India, China or Japan, and European aggregate tables cannot produce a harmonized country ranking. Use observed cash, outlays and income composition for a stated stress question; do not treat age alone as a sufficient capacity or allocation rule.')]

executive=[Paragraph('Research update',styles['ReportTitle']),Paragraph('Age, willingness and liquid-budget resilience<br/>Employer executive brief | November 20, 2026',styles['ReportSubtitle'])]
for title,body in brief:executive.append(p('<b>'+title+'.</b> '+body))
write('fixed_income_executive_brief_2026-11-20.pdf',executive)
(HERE/'EXECUTIVE_SUMMARY.txt').write_text('Age, willingness and liquid-budget resilience\nNovember 20, 2026\n\n'+'\n\n'.join(title+'\n'+body for title,body in brief)+'\n',encoding='utf-8')

story=[Paragraph('Age, willingness and liquid-budget resilience',styles['ReportTitle']),
    Paragraph('Integrated household evidence and allocation validation<br/>November 20, 2026 | Formal research report',styles['ReportSubtitle'])]
story += [p('<b>'+title+'.</b> '+body) for title,body in brief]
story += [PageBreak(),heading('1. Data and published-method reconstruction'),
    p('SCF jointly observes risk responses, asset balances, income components, expenses and survey-design information. Eligible ages are 20-89: 6,194 households in 2016, 5,719 in 2019, 4,557 in 2022 and 4,325 in 2025, before outcome-specific complete-case restrictions. These are independent cross-sections, not a panel of the same households.'),
    p('Bhutta and Dettling (2018) supplies the published accessible-assets/recurring-expenses approach. Our approximate 2016 reconstruction gives 41.02% with three months of coverage and 30.17% with six months, versus published 40% and 28%. Differences remain; this is not an exact author-code replication. The prior crosswalk lists expense-imputation and population differences.'),
    figure('01_us_age_profiles'),
    p('<b>Definitions.</b> Willingness is observed X3014 categories 1-3 versus no risk. Cash is LIQ; marketable assets are STOCKS+BOND+NMMF. The 2025 outlay denominator is TOTSPENDNH/12+RENT+TPAY. Retirement balances, housing, CDs and savings bonds are excluded. A zero marketable balance does not mean no investment ownership. The cross-wave prediction target uses one common age-independent expense reconstruction.'),
    p('<b>Inference.</b> Estimates pool five imputations. Covariance combines official 999-replicate variation on implicate 1 and 1.2 times between-imputation covariance. Age spline knots are 45 and 65; demographic, financial and income-composition specifications are separate. Normal intervals are approximate and generally pointwise. Controls do not identify causal aging effects.'),
    p('Sources: Federal Reserve SCF documentation and 2025 outline; Bhutta and Dettling (2018). Full links and variable crosswalks are in the executed notebook.',True)]
story += [PageBreak(),heading('2. Chronological prediction across US survey waves'),
    p('Weighted logits fit earlier waves and predict the next: 2016 to 2019, 2016+2019 to 2022, and 2016+2019+2022 to 2025. Each training wave receives equal total weight. Models compare intercept, age, income/wealth, and income/wealth plus age. No later-wave outcomes enter fitting.'),
    figure('02_chronological_prediction'),
    p('<b>Result.</b> Age improves the financial model in all three held-out waves for both targets. Willingness Brier improvements are 0.01735, 0.01204 and 0.01076; coverage improvements are 0.00492, 0.00436 and 0.00445. The six tests survive Holm adjustment. Positive differences mean lower squared probability error after adding age.'),
    p('Test intervals include held-out survey and MI uncertainty conditional on fitted models. Full training-sample uncertainty is not included. Financial features share ingredients with the liquidity outcome. Later-wave descriptive outcomes were previously inspected: these are retrospective chronological tests, not an untouched prospective lockbox. Prediction across cross-sections neither identifies within-person aging nor validates a latent lifetime-capacity scale.'),
    p('Supporting files: age_out_of_wave_scores.csv, age_out_of_wave_coefficients.csv and age_transport_design.json. All model AUC and log-loss diagnostics are retained.',True)]
story += [PageBreak(),heading('3. Shock-specific resilience and income composition'),
    p('The primary one-year scenario applies a 40% stock loss and 10% bond loss to a hypothetical 60/40 marketable portfolio. Cash is intact. Earned income stops for six months, pensions/transfers continue, and no new borrowing or asset appreciation is assumed. A pass requires all monthly outlays funded and three months of terminal reserves. Gross-to-net factors 0.70/0.85/1.00 and alternative expense definitions are retained as sensitivities.'),
    figure('03_shock_and_adjustment'),
    p('<b>Result.</b> The 2025 income/wealth-adjusted older-age contrast under earned-income interruption is +16.51 points (11.46 to 21.56). Adding the earned-income share yields +0.37 points (-6.43 to 7.17). Stopping all income instead gives -3.59 points (-8.01 to 0.82) before that additional control. This supports a shock-specific income-composition interpretation, not a causal mediation estimate or a general capacity advantage.'),
    p('Recurring income excludes interest, dividends, capital gains and PENACCTWD retirement-account draws. This prevents portfolio returns or account withdrawals being counted twice. Cash outlays include debt principal and therefore are not interpreted as consumption utility. These stress parameters are investigator-defined, not a formula taken from a paper.'),
    p('Supporting files: budget_age_contrasts.csv, budget_age_profiles.csv and household_input_manifest.json.',True)]
story += [PageBreak(),heading('4. Willingness and financial resilience'),
    figure('04_willingness_resilience_association'),
    p('We estimate willingness differences associated with meeting each threshold, controlling for age, demographics, income and net wealth. Cash coverage is positively associated with willingness in every wave. In 2025 its adjusted difference is +7.35 points (4.36 to 10.34). Earned-interruption stress gives +1.66 points (-1.49 to 4.81), while all-income interruption gives +8.39 points (4.83 to 11.94).'),
    p('The relationship is not absent, but it is not invariant to measurement. The stress test identifies a particular budget ability, while the survey records a stated preference. Common unobserved factors, reverse causation and adjustment choices remain. We do not infer a CRRA coefficient, a suitable stock allocation, or a causal preference effect from these differences.'),
    p('Supporting file: willingness_budget_adjusted.csv. Intervals here are pointwise; the family is exploratory.',True)]
story += [PageBreak(),heading('4a. Independent prospective criterion: SHED'),
    p('We reran the existing SHED analysis using 2018/2019 and 2024/2025 public files. The Federal Reserve documents shedid linkage across waves and a panel weight for recontact respondents. The matched 2024-2025 analysis has 4,299 eligible respondents.'),
    figure('08_shed_prospective_criterion'),
    p('A three-month emergency fund reported in 2024 predicts 6.72 percentage points fewer unpaid bills in 2025 after demographics, income, baseline unpaid bills and income stability (HC3 interval -9.17 to -4.27). Weighted unadjusted unpaid-bill rates are 24.00% without the baseline fund and 5.87% with it. These group differences are not treatment effects.'),
    p('Five-fold respondent-held-out Brier loss falls from 0.097078 to 0.096140; log loss falls from 0.324957 to 0.320628. No interval is claimed for the cross-validation difference. HC3 coefficient intervals are model-based, not full complex-survey uncertainty. This is prospective criterion evidence for an emergency-fund proxy, not direct validation of the new SCF stress formula.'),
    p('The 2018-2019 unweighted retained-panel fund-change/willingness-change coefficient is 0.059 (interval -0.142 to +0.260; n=4,211). It does not establish that better liquidity changes preferences. The absence of longitudinal weights for that older analysis limits population interpretation.'),
    p('Sources: Federal Reserve SHED data, FAQ and 2025 codebook. Supporting files are retained in evidence_shed/.',True)]
story += [PageBreak(),heading('5. Survey-calibrated portfolio budget scenarios'),
    p('Sixteen weighted mean templates retain joint age, cash coverage and willingness cells. A fixed 12-month stationary bootstrap generates 2,000 fit paths and 5,000 disjoint evaluation paths from matched three-asset public/WRDS histories, May 1953-December 2024. Horizons are 1/5/10 years. Income and outlays remain frozen except the six-month interruption. This is not an estimated retirement or career model.'),
    figure('05_template_funding',6.8),
    p('A reserve-constrained rule is selected from six candidates using a simultaneous training probability bound and evaluated independently. Under 10-year WRDS compound stress, 12 of 16 mean templates qualify; four do not. Funding improves versus the age glidepath in two templates, with ties in the others. All income-maintained mean templates fund outlays. These favorable archetype outcomes do not establish population performance or a general welfare gain.'),
    p('Only net income surplus/deficit crosses the portfolio boundary; executed trades pay a 5bp half-spread. No survey-willingness constraint is estimated, so this rule is not an individual suitability recommendation. Paired intervals are conditional Monte Carlo uncertainty, not model or household-estimation uncertainty.',True)]
story += [PageBreak(),heading('6. Why outcomes at mean inputs are not population estimates'),
    figure('06_nonlinear_aggregation',6.8),
    p('Actual household stress prevalence is computed household by household with official survey inference. It can differ substantially from the binary result at a cell mean because asset distributions are skewed and funding constraints are nonlinear. For example, the young cash-rich/no-risk mean template passes, while only 38.85% of households in its source cell pass the same deterministic scenario.'),
    p('Accordingly, we do not weight the 16 simulated success rates to claim national funding success. Household-level age and stress results, conditional template experiments, and return-model tests answer different questions. The gap audit is retained so a reviewer can see the effect directly.'),
    p('Supporting files: actual_household_cell_stress.csv, nonlinear_aggregation_audit.csv, household_templates.csv and household_profile_estimates.csv.',True)]
story += [PageBreak(),heading('7. Corrected WRDS allocation evidence'),
    figure('07_corrected_market_evidence'),
    p('The initial +0.61% age-plus-flow CE estimate was superseded: a mismatched six-asset universe changed automatic block-length fitting. The corrected matched three-asset difference is +0.1041% (-0.0783% to +0.3289%). Only 56% of 100 training-history refits are positive. A stable CE advantage is not established.'),
    p('At 5% real annual withdrawals, a Treasury-only source replacement changes best 30-year success from 89.23% to 90.71% in the 2002-2013 calibration. All-CRSP 2002-2024 gives 88.73%. CE and success selection choose 35% and 5% bonds respectively; independent evaluation gives +9.69% CE but -1.59 percentage points of success for the CE rule. No universal bond floor follows.'),
    p('The earlier extension retains 26 sensitivity configurations, 100 refits and nonoverlapping replay tests: nine five-year, four ten-year and two twenty-year periods per dataset. The long-horizon sample is small. CPI availability is modeled using publication lags on revised extracts, not archived real-time data. The full WRDS notebook contains exact specifications and licensed-source coverage.'),
    p('The zero-holdings continuation correction leaves the saved matched frontier and signed-flow results exactly reproduced. The complete legacy demonstration was also rerun: nine forward summaries change. Lifecycle-adaptive annual CE falls by $2.08, mean cumulative unmet outlays rise by $10.31, and success stays 88.4%. Other numerical fields, including replay and experiments, agree within the recorded tolerance. Corrected outputs and independent accounting/optimization tests are supplied.',True)]
story += [PageBreak(),heading('8. International evidence and comparability')]
countries=[('United States','4-wave SCF microdata; age prediction and defined liquidity/stress outcomes.'),
('Italy','SHIW 2016/2022 microdata: lower adjusted willingness; adjusted liquidity advantage persists in 2016, inconclusive in 2022.'),
('India','SEBI random listing sample: oldest-minus-Gen Z willingness -6.26 points; state-cluster interval -9.06 to -3.46. Capacity not observed.'),
('Spain / Germany / France','HFCS age aggregates for assets, wealth, debt burden and budget surplus; no joint willingness/capacity estimates.'),
('Netherlands / Austria','HFCS aggregates only for the target joint analysis; panel literature remains separate evidence.'),
('Belgium / Portugal','HFCS aggregate context; harmonized household capacity unestimated.'),
('China','Author subset: negative recorded willingness-age association; unresolved response coding and no national weights.'),
('Japan','Selected investor subset; risk-score interpretation unresolved; no comparable liquid-budget capacity.'),
('United Kingdom','Published adviser-client evidence; no newly executed national regression.')]
table=Table([[p('<b>Country / group</b>',True),p('<b>Evidence and boundary</b>',True)]]+[[p(escape(a),True),p(escape(b),True)] for a,b in countries],colWidths=[135,387])
table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e8f0f3')),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#d0dce1')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
story += [table,Spacer(1,12),p('Thirteen countries are covered at unequal evidence levels. Reference-person age, response wording, expense scope, selection and survey period differ. Public separate medians cannot recover household ratios, and no country ranking or cultural mechanism is identified.'),
    p('India reproduces rounded published listing-sample risk benchmarks. Its saving allocations are flows, not emergency balances. In the smaller main-survey state-cluster sensitivity, the oldest-cohort interval includes zero. These results are retained rather than averaged into a single international effect.'),
    p('Sources: Banca d\'Italia SHIW; SEBI Investor Survey 2025; ECB HFCS 2021/2023; country_evidence_inventory.csv and europe_reference_periods.csv. Exact URLs and caveats appear in the notebook.',True)]
story += [PageBreak(),heading('9. References, verification and reproduction')]
refs=[
('Federal Reserve SCF documentation','https://www.federalreserve.gov/econres/scf-documentation.htm'),
('Federal Reserve SHED data and documentation','https://www.federalreserve.gov/consumerscommunities/shed_data.htm'),
('Bhutta and Dettling (2018), expense-based liquidity','https://www.federalreserve.gov/econres/notes/feds-notes/assessing-families-liquid-savings-using-the-survey-of-consumer-finances-20181119.html'),
('Kim, Hanna and Ying (2021), SCF risk measurement','https://doi.org/10.1891/JFCP-19-00022'),
('Dohmen et al. (2017), Risk Attitudes Across the Life Course','https://doi.org/10.1111/ecoj.12322'),
('Lusardi, Schneider and Tufano (2011), financial fragility','https://www.nber.org/papers/w17072'),
('Kaplan, Violante and Weidner (2014), liquid wealth','https://www.nber.org/papers/w20073'),
('Faiella (2008), SHIW variance, equation 11','https://www.bancaditalia.it/pubblicazioni/temi-discussione/2008/2008-0662/en_tema_662.pdf'),
('Brooks et al. (2018), older investors and willingness','https://doi.org/10.1016/j.irfa.2017.12.008'),
('SEBI Investor Survey 2025','https://www.sebi.gov.in/reports-and-statistics/research/jan-2026/investor-survey-2025-_99170.html'),
('ECB Household Finance and Consumption Survey','https://www.ecb.europa.eu/stats/ecb_surveys/hfcs/html/index.en.html'),
('China public author subset','https://doi.org/10.1371/journal.pone.0296100'),
('Japan public author subset','https://doi.org/10.1371/journal.pone.0315622')]
for title,url in refs:
    story.append(p('<link href="'+url+'" color="#1b617e">'+escape(title)+'</link>',True))
story += [Spacer(1,8),p('The delivered English notebook is executed, includes numerical tables, figures and formulas, and runs using aggregate artifacts without WRDS. Source files and public snapshots support public-model reproduction. Licensed CRSP/TRACE inputs and credentials are excluded. Recomputing those market experiments requires independently entitled access.'),
    p('The tested Windows setup_windows.ps1 installs the public platform in one command. Its gold-unavailable fallback is explicitly an ex-gold variant. Final checks pass 124 backend/accounting, six household, 230 frontend unit and 26 browser tests. Reproduction receipts, source/input hashes and a package manifest are supplied. Employer deployment and responses remain external dependencies; no external message or deployment is claimed. No recording or transcript was located in the sources previously searched.'),
    p('Read integrated_research.html first; use integrated_research.ipynb to inspect executable steps. REPRODUCE.txt documents the fresh setup, public SCF helper layout, downloads and all rerun commands. verification.json records final checks. Prior dated household/public/WRDS reports remain available for the audit trail.')]
write('fixed_income_integrated_report_2026-11-20.pdf',story)
print('Formal PDF report and executive brief built')
