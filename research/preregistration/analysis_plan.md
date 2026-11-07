# LIFECYCLE v2 pre-analysis plan

Registered 2026-11-07, before any v2 study was run. Machine-readable version: `hypotheses_v2.json`
(read by `lifecycle.studies.evidence`).

1. **Confirmatory family.** H1-v2 ... H12 (table in `hypotheses_v2.json`). Each has a null, an estimand, a
   benchmark and a falsification rule. Verdicts are computed automatically from persisted study runs.
2. **Inference.** Paired common-random-number differences; delta-method and path-pair bootstrap CIs for
   dCE; Wilson CIs for Monte Carlo success probabilities (iid conditional on the fitted model only); no
   binomial CI on overlapping historical cohorts; joint path bootstrap of the whole success surface for
   b_min. Holm and Benjamini-Hochberg adjustments over the computed family.
3. **Evidence grades.** `not_computed`, `diagnostic`, `conditional`, `robust`, `contradicted`, `invalid`
   (brief 13.2). "Supported" requires CI excluding zero, Holm-adjusted p <= 0.05 and materiality
   (dCE >= 0.1%). "Robust" additionally requires at least four passing evidence dimensions
   (Monte Carlo, parameter, model, historical, OOS, source quality).
4. **Holdout.** Policies are fitted on seed-set A and scored on disjoint seed-set B; the chronological
   walk-forward (splits 1975 / 1990 / 2005) fits on data before the split and scores on later cohorts.
5. **Negative results** are reported with the same prominence as positive ones.
