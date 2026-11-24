"""Package executed reports and aggregate evidence, excluding licensed inputs."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import nbformat
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BASE = "4b0c23ec63f760feb8bcfbaecddd5746921f21d4"
PUBLIC = ROOT / "research/followup_2026_11_19"
WRDS = ROOT / "research/wrds_validation_2026_11_19"
commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
patch = subprocess.check_output(["git", "diff", "--binary", BASE, "HEAD", "--", ".",
    ":(exclude)research/followup_2026_11_19", ":(exclude)research/wrds_validation_2026_11_19"], cwd=ROOT)
(PUBLIC / "source_changes.patch").write_bytes(patch)
for folder, name in [(PUBLIC, "fixed_income_validation"), (WRDS, "wrds_validation")]:
    notebook = nbformat.read(folder / (name + ".ipynb"), as_version=4)
    code = [c for c in notebook.cells if c.cell_type == "code"]
    assert all(c.execution_count is not None for c in code)
    assert not any(o.output_type == "error" for c in code for o in c.outputs)
    inputs = {str(p.relative_to(folder)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*")) if p.is_file() and p.name != "validation_manifest.json"}
    manifest = {"date": "2026-11-19", "starting_commit": BASE, "continuation_commit": commit,
        "engine_semantic_version": "2.3", "raw_wrds_data_included": False, "inputs": inputs}
    (folder / "validation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
frontier = pd.read_csv(WRDS / "matched_frontier_summary.csv")
early = frontier[frontier.window.eq("early") & frontier.withdrawal_rate.eq(.05)].set_index("dataset")
modern = frontier[frontier.window.eq("modern") & frontier.withdrawal_rate.eq(.05)].set_index("dataset")
extended = json.loads((WRDS / "wrds_extended_runs.json").read_text())
signed = json.loads((WRDS / (extended["signed_flow"]["run_id"] + ".json")).read_text())
delta = signed["policies"]["oos_full_vs_age"]
history = pd.read_csv(WRDS / "chronological_summary.csv")
history = history[history.dataset.eq("wrds")]
allocation = pd.read_csv(WRDS / "allocation_objective_summary.csv")
a5 = allocation[allocation.withdrawal_rate.eq(.05)].iloc[0]
rob = WRDS / "robustness"
refit = pd.read_csv(rob / "history_refit_scores.csv")
full_refit = refit[refit.policy.eq("full")].relative_resources_ce
sensitivity = pd.read_csv(rob / "sensitivity_scores.csv")
seed_results = sensitivity[sensitivity.generator.eq("bootstrap") & sensitivity.requested_block.isna()
    & sensitivity.cost_half_spread_bps.eq(0) & sensitivity.bond_step.eq(.1) & sensitivity.gamma.eq(4)
    & sensitivity.resource_floor.eq(1000) & sensitivity.weighting.eq("original_age_weights")
    & sensitivity.flow_grid.eq("full") & sensitivity.policy.eq("full")].relative_resources_ce
readme = f"""Fixed-income allocation: completed public and WRDS validation
November 19, 2026 (America/New_York)

Read research/wrds_validation_2026_11_19/wrds_validation.html for the new WRDS findings.
Read research/followup_2026_11_19/fixed_income_validation.html for the original audit and public-data baseline.
Both English notebooks are executed and include methods, citations, numerical tables and figures.

New findings

At 5% initial annual real withdrawals, the 2002-2013 calibration gives a highest 30-year spending-success
probability of {early.loc['public','best_success']:.2%} for the public reconstruction and {early.loc['treasury_only','best_success']:.2%} when only Treasury
returns are replaced by CRSP. The latter reaches the 90% target first at {early.loc['treasury_only','minimum_bond_share']:.0%} bonds on the tested grid.
Using all CRSP core inputs over 2002-2024 gives {modern.loc['wrds','best_success']:.2%} at the best tested allocation. The result depends
on the return source, sample and scenario generator; there is no supported universal bond minimum.

The corrected three-asset WRDS age-plus-flow rule changes resources CE by {delta['delta']:.2%} versus age-only
(95% paired interval {delta['lo']:.2%} to {delta['hi']:.2%}, including zero). Five simulation seeds give a range
of {seed_results.min():.2%} to {seed_results.max():.2%}. The initial six-asset 0.61% estimate is superseded: unused Treasury
assets changed the automatically fitted block length and prevented a matched comparison.

Only {(full_refit>0).mean():.0%} of 100 training-history refits produce a positive CE difference. The central refit range is
{full_refit.quantile(.025):.2%} to {full_refit.quantile(.975):.2%}; this is sensitivity conditional on a fixed future model, not a
general confidence interval. Completed nonoverlapping tests contain nine five-year, four ten-year
and two twenty-year periods per dataset. No consistent superiority of the conditional rule is established.
At 5% withdrawals, utility and spending-success optimization select {a5.ce_selected_bonds:.0%} and {a5.success_selected_bonds:.0%} bonds respectively.
The utility policy gains {a5.ce_gain:.2%} CE and changes success by {(a5.ce_policy_success-a5.success_policy_success)*100:.2f} percentage points on independent test paths.

These return-based experiments do not estimate household age effects on risk tolerance or capacity.

Completed checks

12 matched-window frontier studies; 384 earlier chronological age/flow cells; four verified extraction hashes;
zero invalid restricted returns or duplicate month/series records; exact frontier and signed-flow
reproduction; 111 backend tests and four analytical robustness tests. The extension adds 26 sensitivity
configurations, 100 history refits and 900 policy/flow outcomes across 30 complete nonoverlapping periods
(15 per dataset; horizons share months). The earlier frontend checks remain 230 unit tests, 26 browser tests,
type-check and production build passed. The existing lint warning and six dependency advisories remain
documented in the public report. The full 12-sleeve multi-asset study and Permanent Portfolio now run.

Reproduction

The source patch at research/followup_2026_11_19/source_changes.patch applies to {BASE}.
Clone the original project, check out that commit, apply the patch, and copy the two research output
folders into its research directory. Aggregate notebook execution does not require WRDS. Recomputing
restricted return-based studies requires an entitled WRDS academic account and the documented Cloud
extraction process. The raw CRSP/TRACE files are excluded from this package and Git. Review the notebook
for source-specific date ranges, partial-inception-month exclusions and uncertainty definitions.

WRDS access is complete. Employer installation still awaits the employer reply and GitHub username.
No external messages have been sent. No meeting recording or transcript was located in the sources searched.
"""
(WRDS / "README.txt").write_text(readme, encoding="utf-8")
# Rebuild this folder's manifest after writing its entry-point README.
manifest = json.loads((WRDS / "validation_manifest.json").read_text())
manifest["inputs"]["README.txt"] = hashlib.sha256((WRDS / "README.txt").read_bytes()).hexdigest()
(WRDS / "validation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
target = ROOT.parent / "outputs/lifecycle_followup_2026-11-19.zip"
forbidden = {"mcti.csv", "msix.csv", "etfs.csv", "credit.csv", "transfer.txt", "wrds_inputs.zip", "panel.parquet"}
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("README.txt", readme)
    for folder in [PUBLIC, WRDS]:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                assert path.name not in forbidden
                archive.write(path, str(path.relative_to(ROOT)))
    for path in sorted((ROOT / "research").glob("*.py")):
        archive.write(path, str(path.relative_to(ROOT)))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert not any(Path(name).name in forbidden for name in archive.namelist())
for folder in [PUBLIC, WRDS]:
    manifest = json.loads((folder / "validation_manifest.json").read_text())
    assert all(hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest for name, digest in manifest["inputs"].items())
print(json.dumps({"archive": target.name, "bytes": target.stat().st_size,
    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "restricted_observations_included": False}, indent=2))
