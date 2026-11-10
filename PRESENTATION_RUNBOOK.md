# Presentation runbook: rebuild the runs, export the figures, run the ablations

This is the order to do things tonight. Each step says what to run, how long to expect, and how to tell that it worked.

The code references are to the latest app code (branch `claude/unify-lifecycle-app`, commit `6869a2b`). Run every command from the repository root unless a step says otherwise.

> **Order matters.** Each app page shows the *newest finished run* of its study, and that choice isn't saved in the URL. If you run ablations against the same data folder, the pages will start showing ablation results. So:
> 1. Rebuild the baseline runs.
> 2. Export the figures.
> 3. Only then run the ablations, in a **copy** of the data folder (Step 5).

---

## Step 0 — Before you start (5 min)

```bash
git checkout claude/unify-lifecycle-app && git pull
```

```bash
make setup
```

```bash
make test-backend
```

- Check that `.env` contains `WRDS_USERNAME` and `WRDS_PASSWORD`.
- Back up the current runs, so you can return to them if something goes wrong:

```bash
cp -r data/runs data/runs_backup_$(date +%Y%m%d)
```

---

## Step 1 — Rebuild the panel with the currency basket (one Duo push)

```bash
make ingest-wrds OFFLINE=1
```

`OFFLINE=1` takes the public series (including the Nov 7 currency snapshot) from `snapshots/public`. Only WRDS goes over the network, so approve the Duo push when it arrives.

**Check it worked:** the build ends with a new catalog hash. Then open the Methodology page (or Overview › Data health, figure OV-07) and confirm the coverage grid now shows `fx_basket`. If it doesn't, Step 3's multi-asset run will fail with "universe unavailable". In that case, skip MA-04 and use the fallback story (PP-02/PP-12 and HR-10).

---

## Step 2 — Rerun the nine core studies (`seed-v2`)

```bash
make seed-v2
```

This runs `frontier`, `signed_flow`, `rebalance`, `scenario_lab`, `optimize`, `compare_v2`, `asof`, `permanent` and `evidence` (`backend/lifecycle/cli.py:127`), and writes the run IDs to `research/results/v2_run_ids.json`. `seed-v2` doesn't need `--force`, because the new catalog hash gives every spec a new run ID.

**Check it worked:** every line printed says `done`. If `permanent` fails because gold is unavailable, it automatically reruns without gold on `core_duration`. Note this if it happens, because PP-02's numbers will then be the no-gold variant.

---

## Step 3 — Run the three studies `seed-v2` leaves out

These are Dynamic Multi-Asset (MA-04 to MA-10), Historical Replay (HR-01, HR-08, HR-10) and the Lifecycle Simulator. Either click **Run default** on Optimize › Multi-Asset, Lifecycle › Replay and Lifecycle › Simulator, or run all three in one go:

```bash
cd backend && .venv/bin/python -c "
from lifecycle.studies import registry as S
from lifecycle.runs import executor, registry
for k in ['multi_asset', 'historical_replay', 'lifecycle_sim']:
    rid = executor.run_sync(k, S.spec_model(k)(), 'default ' + k)
    r = registry.get(rid) or {}
    print(k, rid, r.get('status'), (r.get('error') or '')[:300])
"; cd ..
```

**Check it worked:** all three print `done`. If `multi_asset` fails, read its error: it names the missing sleeve. The default public tier needs equity, rates, credit, `fx_basket` and cash.

---

## Step 4 — Export the figures

Start the app with `make dev`, open it once in a browser, and check that each page shows the run IDs from Steps 2–3. Then use either method below.

### 4a. Manual (fine for a few figures)

- **Switch the app to light mode first** (sun/moon button in the top bar). The charts have a transparent background, so a dark-mode export has light text that disappears on a white slide.
- **Image:** hover the chart and click the camera icon in the Plotly toolbar. This saves a PNG at on-screen size. For a sharper image, zoom the browser to 200% before you click.
- **Tables and diagrams** (CO-06, PP-02, OV-02, MT-01) have no camera icon. Use the OS screenshot tool.
- **The numbers behind a chart:** the download icon on each card gives `…/v1/studies/run/<run_id>/export?format=csv&block=<block>`. The Runs › Reproduce & Export page has the full study JSON and CSV. Put these in an appendix or a backup slide.

### 4b. Scripted (recommended: one command, all figures, high resolution, with run IDs)

Save the script in Appendix A as `web/export-figures.mjs`, then:

```bash
cd web && node export-figures.mjs
```

- It writes `research/figures/<ID>.png` at 3× resolution in light mode, plus `research/figures/manifest.json`, which records the run ID each figure came from.
- To redo only some figures, pass their IDs: `node export-figures.mjs WL-01 WL-02`.
- Each image is the whole card: ID, title, data-class tag and run ID. Crop the header in the slide if you want it cleaner. Keep the run ID in the slide footnote.
- **How to read the output:** `ok` means exported. `EMPTY` means the card rendered an "unavailable" state, so don't use it. `FAIL … Timeout` means the study has no finished run; go back to Step 2 or 3.
- I tested this script against the app on synthetic data. WL-01/02/04/06 and MT-01 exported correctly. CO-06 and HR-10 failed only because that test setup had no compare or replay runs, which is the expected `FAIL`.

### Figure → page → section (for 4a, or if the script misses one)

| Figure | URL | Slide use |
|---|---|---|
| OV-02 Lifecycle continuum strip | `/?section=status` | Framing |
| MT-01 Pipeline diagram | `/methodology?section=pipeline` | Data & method |
| OV-07 Data coverage grid | `/?section=health` | Data & method |
| WL-01 Survival heatmap | `/withdrawal-lab?section=overview` | Core result |
| WL-02 Bond necessity frontier | `/withdrawal-lab?section=overview` | Threshold deliverable |
| WL-03 Survival curves | `/withdrawal-lab?section=sustainability` | Backup |
| WL-04 Max sustainable withdrawal | `/withdrawal-lab?section=sustainability` | Hump shape |
| WL-05 CE vs survival optimum | `/withdrawal-lab?section=utility` | Behavioural vs mechanical |
| WL-06 Sensitivity forest | `/withdrawal-lab?section=robustness` | Robustness |
| WL-07 First shortfall | `/withdrawal-lab?section=outcomes` | Live demo |
| WL-11 Funding gap drilldown | `/withdrawal-lab?section=paths` | Live demo |
| WL-12 Allocation ranges by phase | `/withdrawal-lab?section=bond-necessity` | Recommendation |
| CO-01 Paired CE forest, CO-06 Trade-off table | `/compare?section=policies` | Heuristics vs 60/40 |
| OP-02 Optimal surfaces | `/optimize?section=surfaces` | Accumulation vs decumulation |
| OP-14 Growth share by age | `/optimize?section=policy-family` | Accumulation vs decumulation |
| PP-02 Scorecard | `/permanent-portfolio?section=overview` | Multi-asset |
| PP-12 Ablation / Shapley | `/permanent-portfolio?section=composition` | Multi-asset (gold's role) |
| MA-01 to MA-03 | `/permanent-portfolio?section=multi-asset` | Multi-asset (after Step 3) |
| MA-04 to MA-10 | `/optimize?section=multi-asset` | Multi-asset (after Step 3) |
| HR-01, HR-08, HR-10 | `/lifecycle-flows?section=replay` | Historical replay |
| RS-02 Evidence heatmap | `/research?section=hypotheses` | What's established |
| RS-06 Disagreement forest | `/research?section=uncertainty` | Robustness |

**After exporting, refresh the numbers in your slides.** The new panel adds the currency basket, which changes the catalog hash and therefore every run. The numbers in my earlier summary come from the Nov 7 runs and will move slightly. Re-read the headline cells from the new WL-01 and CO-06 (or from `research/ablations/ablation_summary.csv` after Step 5, row `A0_baseline`).

---

## Step 5 — Ablation studies

### What you already have without any extra runs

Several ablations are already part of the default runs. Show these first, because they cost nothing:

| Built-in ablation | Where it is | What varies |
|---|---|---|
| Horizon × target × generator × calibration window | WL-06 forest, RS-06 | T ∈ {10, 20, 30, 40} years; s* ∈ {80, 85, 90, 95}%; bootstrap vs Student-t vs Markov switching; calibration 1953–89 vs 1990–2026 |
| Bond instrument | Withdrawal Lab › Bond necessity | T-bill vs 5Y vs 10Y: Δsuccess and ΔCE by withdrawal rate |
| Risk aversion γ | Withdrawal Lab › Utility | γ ∈ {2, 4, 6, 8}: how the CE-optimal bond share moves (survival is unaffected by γ) |
| Gold / long duration removed | PP-12 Shapley, PP-02 (`pp_no_gold`, `pp_no_long_duration`) | Each sleeve's contribution to PP welfare |
| Duration and cash buffer | Permanent › Composition | 2/5/10/30Y long-bond sleeve; 0–5-year cash reserve |
| Rebalancing rule × cost | Rebalancing pages | 16 rules; costs of 0–20 bps; cadence of 1, 3, 6 or 12 months; 2.5/5/10pp bands |
| Policy comparison across generators and windows | Compare › Robustness | 4 generators; 1977–2001 vs 2002–2026 |
| Multi-asset across generators | MA-10 | Robustness generators |

### New ablations to run (the script in Appendix B)

Each group has one question, and only one factor changes from the baseline per row. The **must** tier is what I'd run tonight. **extra** is for later, or for the paper.

**A. Withdrawal frontier** (WL-01/02/04/05). This supports the threshold claims.

| Row | Changed factor | Why it matters |
|---|---|---|
| A1 seeds 2 and 3, A2 10k paths (must) | Monte Carlo noise | Sets the noise floor. The 95% "bonds necessary" window at 4.0% (15–30% bonds) is narrow. If a different seed moves it, present it as approximate, not as a result. |
| A3 bond = 5Y, T-bill (must) | Bond instrument across the full surface | Does "bonds are necessary at 4%" depend on duration? |
| A4 buy-and-hold (must) | No rebalancing | Separates the hump in WL-04 into diversification vs rebalancing premium. |
| A5 calibration from 1971 / 1982 (must) | Sample | 1982+ is the bond bull market. If the 95% window widens only there, bond necessity rests on falling rates. |
| A6 block length 6 / 60 months | Dependence structure | Long blocks preserve mean reversion and sequence risk. |
| A7 Student-t / Markov (full surface) | Generator | The forest already covers this at r = 5%. This run extends it to every cell. |
| A8 costs of 5 bps | Frictions | Should be small. If it isn't, that's worth knowing. |

**B. Heuristics vs 60/40** (CO-01/06). This supports "conventional rules over-allocate to bonds."

| Row | Changed factor | Why it matters |
|---|---|---|
| B1 withdrawal 3.5% / 5.5% (must) | Spending | Does the target-date CE loss (−15.6% at 4.5%) hold across draw rates, or flip at low draws? |
| B2 γ = 2 / 8 | Risk aversion | A very risk-averse household might rationally prefer target-date. This shows where that crossover is. |
| B3 zero costs | Frictions | Rules out costs as the driver. |

**C. Permanent Portfolio** (PP-02/12). This addresses the "it's just the gold bull market" critique.

| Row | Changed factor | Why it matters |
|---|---|---|
| C1 calibrate to 2011 / from 2012 (must) | Sample split at the 2011 gold peak | The most important new ablation. If PP still beats 60/40 on the 2012–2024 sample, the result isn't just gold's rally. **Caveat:** the post-2012 sample is only about 13 years, bootstrapped over 30, so call it indicative. |
| C2 Student-t | Generator | A fat-tailed i.i.d. model removes the regime persistence gold benefits from. |
| C3 5% draw | Spending | PP has lower expected return, so check whether it survives a higher draw. |

**D. Dynamic multi-asset** (MA-04/05/10). Run this only if Step 3 succeeded.

| Row | Changed factor | Why it matters |
|---|---|---|
| D1 bootstrap instead of Markov (must) | Generator | The default generator is regime-switching, which flatters regime-based policies. H8 already says regime conditioning doesn't help out of sample. This checks whether that holds on a generator with no regimes. |
| D2 trend lookback 6 months, D3 target vol 12% | Policy tuning | If rankings flip under small tuning changes, dynamic policies are over-fitted. |
| D4 costs of 10 bps | Frictions | Dynamic policies trade more, so they're the most sensitive. |
| D5 full data tier | Universe | Only works if commodities and HY are in the panel. Expect a failure otherwise. |

**E. Historical replay** (HR-10).

| Row | Changed factor | Why it matters |
|---|---|---|
| E1 expanding universe (must) | Sleeves enter when they get history | Lets gold in from late 2007, so the classic PP stops showing "unavailable". |
| E2 start in 2010 (must) | Start date | 2007 puts the 2008 crash in year 1. Tests how much of the result is that single sequence. |
| E3 estimation window of 60 months / expanding | Point-in-time estimation | |
| E4 no tactical tilt, E5 costs of 10 bps | Implementation | Trend-following made 120 rebalances. Does it survive higher costs? |

**F. Signed flow** (OP-02/14), extra tier. Horizon of 10 or 30 years and γ = 8, to test whether "10–30% bonds everywhere" holds. This matters because H1/H2 are already fragile.

### How to run them

```bash
cp -r data data_ablation
```

Save Appendix B as `backend/run_ablations.py`. Then validate the specs without running anything:

```bash
cd backend && .venv/bin/python run_ablations.py --dry-run --tier all
```

Run the must tier:

```bash
cd backend && LIFECYCLE_DATA_DIR=../data_ablation .venv/bin/python run_ablations.py --tier must
```

Or a subset by study or row name, for example frontier first:

```bash
cd backend && LIFECYCLE_DATA_DIR=../data_ablation .venv/bin/python run_ablations.py --only frontier
```

- `LIFECYCLE_DATA_DIR` keeps every ablation run out of the app's data folder, so the presentation pages still show the baselines.
- The baseline row of each group is an instant cache hit, because the copied registry already has it.
- **Outputs:** `research/ablations/ablation_summary.csv` has one row per run: run ID, status, the study's summary fields, and for the frontier the headline cells, b_min at 90/95%, the maximum sustainable r and the CE-vs-survival gap. There is also one JSON file of derived results per run.
- The CSV is rewritten after every run, so stopping partway keeps what finished.
- **Timing:** I didn't time these on WRDS data. Run `--only frontier` first and time it. `A2_paths_10k` is the slowest row, about 5× a normal frontier run. Drop it if you're short on time and keep the two seed rows.
- **Testing done:** I validated all 42 specs against the study models, and checked the frontier extraction on a synthetic-data run.

### How to present the ablations (one slide plus a backup)

1. **Noise floor first.** Report how far A0, A1 and A1-seed-3 differ on each headline number. Treat any ablation that moves a number by less than that amount as "no effect".
2. **One table**, with rows = the ablations and columns = the headline numbers: S(4%, 20%), b_min at 95% and 4%, the maximum sustainable r at 95%, the CE-vs-survival gap, and target-date ΔCE. Colour each cell by whether it moved beyond the noise floor.
3. **Sentences for the slide:**
   - "Bond necessity at 95% holds / doesn't hold outside 1982+."
   - "PP's edge survives / disappears after the 2011 gold peak."
   - "Regime policies don't beat 60/40 even on their own generator."
4. **To show an ablation as a chart** (for example WL-01 for `A5_calib_post1982` next to the baseline), don't submit it in the presentation app. That would make it the page's newest run. Instead, start a second API on the ablation folder:

   ```bash
   LIFECYCLE_DATA_DIR=data_ablation make dev
   ```

   Then on the page:
   1. Click **Edit spec**.
   2. Paste the `"spec"` object from `research/ablations/<row>_<id>.json`.
   3. Click **Submit spec**.

   It's a cache hit, so it's instant, and the tab follows that run until you reload. Export the figure with the camera icon (Step 4a).

---

## Step 6 — Before the meeting

- Click through the three live-demo paths once: WL-01 → WL-07/WL-11, Replay HR-01/HR-08, and Runs › reproduce one ID with `make reproduce RUN=<id>`.
- The three runs stuck at "running" since Nov 7 will still be in the registry. They're harmless; just don't click them during the demo.
- Keep `research/figures/manifest.json` open, so you can answer "which run is this?" for any slide.

---

## Appendix A — `web/export-figures.mjs`

Uses the `@playwright/test` package the web app already depends on. If Chromium isn't installed, run `npx playwright install chromium` once.

```js
// Screenshot every presentation figure from the running app (API :8000 + web :3000) as high-res PNGs.
// Run from web/:  node export-figures.mjs            (output: ../research/figures/<ID>.png)
//                 BASE=http://localhost:3000 SCALE=3 THEME=light node export-figures.mjs
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

const BASE = process.env.BASE ?? "http://localhost:3000";
const API = process.env.API ?? "http://localhost:8000";
const SCALE = Number(process.env.SCALE ?? 3);
const THEME = process.env.THEME ?? "light";
const OUT = process.env.OUT ?? "../research/figures";

// [figure id, page path, section]
const FIGS = [
  ["OV-02", "/", "status"], ["OV-07", "/", "health"], ["MT-01", "/methodology", "pipeline"],
  ["WL-01", "/withdrawal-lab", "overview"], ["WL-02", "/withdrawal-lab", "overview"],
  ["WL-03", "/withdrawal-lab", "sustainability"], ["WL-04", "/withdrawal-lab", "sustainability"],
  ["WL-05", "/withdrawal-lab", "utility"], ["WL-06", "/withdrawal-lab", "robustness"],
  ["WL-07", "/withdrawal-lab", "outcomes"], ["WL-11", "/withdrawal-lab", "paths"],
  ["WL-12", "/withdrawal-lab", "bond-necessity"],
  ["CO-01", "/compare", "policies"], ["CO-06", "/compare", "policies"],
  ["OP-02", "/optimize", "surfaces"], ["OP-14", "/optimize", "policy-family"],
  ["PP-02", "/permanent-portfolio", "overview"], ["PP-12", "/permanent-portfolio", "composition"],
  ["MA-01", "/permanent-portfolio", "multi-asset"], ["MA-02", "/permanent-portfolio", "multi-asset"],
  ["MA-03", "/permanent-portfolio", "multi-asset"],
  ["MA-04", "/optimize", "multi-asset"], ["MA-05", "/optimize", "multi-asset"], ["MA-06", "/optimize", "multi-asset"],
  ["MA-09", "/optimize", "multi-asset"], ["MA-10", "/optimize", "multi-asset"],
  ["HR-01", "/lifecycle-flows", "replay"], ["HR-08", "/lifecycle-flows", "replay"], ["HR-10", "/lifecycle-flows", "replay"],
  ["RS-02", "/research", "hypotheses"], ["RS-06", "/research", "uncertainty"],
];
const only = process.argv.slice(2);
const todo = only.length ? FIGS.filter(([id]) => only.includes(id)) : FIGS;

mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const ctx = await browser.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: SCALE, colorScheme: THEME });
await ctx.addInitScript((t) => { try { localStorage.setItem("theme", t); } catch {} }, THEME);
const page = await ctx.newPage();
const manifest = [];
let current = "";
for (const [id, path, section] of todo) {
  const url = BASE + path + "?section=" + section;
  if (url !== current) {
    await page.goto(url, { waitUntil: "networkidle", timeout: 120_000 });
    current = url;
  }
  const el = page.locator(`section[data-viz-id="${id}"]`).first();
  try {
    await el.waitFor({ state: "visible", timeout: 20_000 });   // not found = that study has no finished run
    await el.scrollIntoViewIfNeeded();
    // let Plotly finish drawing (charts mount lazily and re-layout on resize)
    await page.waitForFunction((sel) => {
      const s = document.querySelector(sel);
      if (!s) return false;
      const p = s.querySelector(".js-plotly-plot");
      return !p || !!p.querySelector(".main-svg");
    }, `section[data-viz-id="${id}"]`, { timeout: 30_000 }).catch(() => {});
    await page.waitForTimeout(1200);
    const runText = (await el.locator("text=/^run [0-9a-f]+/").first().textContent({ timeout: 1000 }).catch(() => null)) ?? "";
    const empty = await el.locator(".border-dashed").count();
    await el.screenshot({ path: `${OUT}/${id}.png`, animations: "disabled" });
    manifest.push({ id, url, run: runText.replace("run ", "").trim() || null, empty_state: empty > 0 });
    console.log((empty ? "EMPTY " : "ok    ") + id, runText);
  } catch (e) {
    manifest.push({ id, url, error: String(e).split("\n")[0] });
    console.log("FAIL  " + id + "  " + String(e).split("\n")[0]);
  }
}
// record which run each page was showing, so every slide can cite its run ID
for (const kind of ["frontier", "compare_v2", "permanent", "multi_asset", "historical_replay", "signed_flow", "optimize", "evidence"]) {
  try {
    const r = await (await fetch(`${API}/v1/studies/${kind}/latest`)).json();
    manifest.push({ study: kind, run_id: r.run_id ?? r.data?.run_id ?? null, catalog_hash: r.catalog_hash ?? r.data?.catalog_hash ?? null, status: r.status ?? r.data?.status });
  } catch { /* API not reachable from node: skip */ }
}
writeFileSync(`${OUT}/manifest.json`, JSON.stringify(manifest, null, 2));
await browser.close();
console.log("wrote", todo.length, "figures to", OUT);
```

## Appendix B — `backend/run_ablations.py`

```python
"""Ablation runner for the LIFECYCLE studies.

Run from backend/ with the project venv, against a COPY of the data dir so the app's pages keep
showing the baseline runs:

    cp -r ../data ../data_ablation
    LIFECYCLE_DATA_DIR=../data_ablation .venv/bin/python run_ablations.py --tier must
    LIFECYCLE_DATA_DIR=../data_ablation .venv/bin/python run_ablations.py --tier all
    .venv/bin/python run_ablations.py --dry-run          # validate every spec, run nothing

Writes ../research/ablations/ablation_summary.csv and one JSON per run (derived results only).
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from lifecycle.studies import registry as studies
from lifecycle.studies.common import StudyData

OUT = Path(__file__).resolve().parents[1] / "research" / "ablations"


def base(kind):
    return studies.spec_model(kind)()


def sub(model, **kw):
    return model.model_copy(update=kw)


def ablations():
    """(tier, study, name, factor, spec). The first row of each study is its baseline."""
    F = base("frontier")
    C = base("compare_v2")
    P = base("permanent")
    M = base("multi_asset")
    H = base("historical_replay")
    G = base("signed_flow")
    rows = [
        # ---- A. frontier: survival surface, b_min, max sustainable withdrawal, CE vs survival optimum
        ("must", "frontier", "A0_baseline", "baseline", F),
        ("must", "frontier", "A1_seed_2", "MC noise", sub(F, scenario=sub(F.scenario, seed=2))),
        ("must", "frontier", "A1_seed_3", "MC noise", sub(F, scenario=sub(F.scenario, seed=3))),
        ("must", "frontier", "A2_paths_10k", "MC noise", sub(F, scenario=sub(F.scenario, n_paths=10_000))),
        ("must", "frontier", "A3_bond_5y", "bond instrument", sub(F, bond="ust_5y")),
        ("must", "frontier", "A3_bond_tbill", "bond instrument", sub(F, bond="tbill")),
        ("must", "frontier", "A4_buyhold", "rebalancing", sub(F, rebalancer="none_buyhold")),
        ("must", "frontier", "A5_calib_post1971", "calibration window",
         sub(F, data=StudyData(universe=F.data.universe, calibration_start="1971-01-01"))),
        ("must", "frontier", "A5_calib_post1982", "calibration window",
         sub(F, data=StudyData(universe=F.data.universe, calibration_start="1982-01-01"))),
        ("extra", "frontier", "A6_block_6m", "bootstrap block length", sub(F, scenario=sub(F.scenario, block_length=6.0))),
        ("extra", "frontier", "A6_block_60m", "bootstrap block length", sub(F, scenario=sub(F.scenario, block_length=60.0))),
        ("extra", "frontier", "A7_iid_student_t", "generator", sub(F, scenario=sub(F.scenario, generator="student_t"))),
        ("extra", "frontier", "A7_markov", "generator", sub(F, scenario=sub(F.scenario, generator="markov_switching"))),
        ("extra", "frontier", "A8_costs_5bps", "trading costs", sub(F, costs=sub(F.costs, half_spread_bps=5.0, commission_bps=1.0))),
        # ---- B. strategy comparison: heuristics vs 60/40
        ("must", "compare_v2", "B0_baseline", "baseline", C),
        ("must", "compare_v2", "B1_w3.5", "withdrawal rate", sub(C, withdrawal=0.035)),
        ("must", "compare_v2", "B1_w5.5", "withdrawal rate", sub(C, withdrawal=0.055)),
        ("extra", "compare_v2", "B2_gamma2", "risk aversion", sub(C, preferences=sub(C.preferences, gamma=2.0))),
        ("extra", "compare_v2", "B2_gamma8", "risk aversion", sub(C, preferences=sub(C.preferences, gamma=8.0))),
        ("extra", "compare_v2", "B3_zero_cost", "trading costs", sub(C, costs=sub(C.costs, commission_bps=0.0, half_spread_bps=0.0))),
        # ---- C. Permanent Portfolio: is it just the gold bull market?
        ("must", "permanent", "C0_baseline", "baseline", P),
        ("must", "permanent", "C1_calib_to_2011", "gold sample split",
         sub(P, data=StudyData(universe=P.data.universe, calibration_end="2011-12-31"))),
        ("must", "permanent", "C1_calib_from_2012", "gold sample split",
         sub(P, data=StudyData(universe=P.data.universe, calibration_start="2012-01-01"))),
        ("extra", "permanent", "C2_student_t", "generator", sub(P, scenario=sub(P.scenario, generator="student_t"))),
        ("extra", "permanent", "C3_withdraw_5", "withdrawal rate", sub(P, withdrawal=0.05)),
        # ---- D. dynamic multi-asset (needs the currency basket in the panel)
        ("must", "multi_asset", "D0_baseline", "baseline", M),
        ("must", "multi_asset", "D1_bootstrap", "generator", sub(M, scenario=sub(M.scenario, generator="bootstrap"))),
        ("extra", "multi_asset", "D2_trend_6m", "signal lookback", sub(M, trend_months=6)),
        ("extra", "multi_asset", "D3_targetvol_12", "risk target", sub(M, target_vol=0.12)),
        ("extra", "multi_asset", "D4_costs_10bps", "trading costs", sub(M, costs=sub(M.costs, half_spread_bps=10.0))),
        ("extra", "multi_asset", "D5_full_tier", "data tier", sub(M, data=StudyData(universe="multi_asset_full"))),
        # ---- E. historical replay: one dated investor
        ("must", "historical_replay", "E0_baseline", "baseline", H),
        ("must", "historical_replay", "E1_expanding_universe", "universe mode", sub(H, universe_mode="expanding")),
        ("must", "historical_replay", "E2_start_2010", "start date", sub(H, start="2010-01")),
        ("extra", "historical_replay", "E3_window_60m", "estimation window", sub(H, estimation_window_months=60)),
        ("extra", "historical_replay", "E3_window_expanding", "estimation window", sub(H, estimation_window_months=None)),
        ("extra", "historical_replay", "E4_no_tactical", "tactical tilt", sub(H, tactical_limit=0.0)),
        ("extra", "historical_replay", "E5_costs_10bps", "trading costs", sub(H, costs=sub(H.costs, half_spread_bps=10.0))),
        # ---- F. signed flow: accumulation vs decumulation
        ("extra", "signed_flow", "F0_baseline", "baseline", G),
        ("extra", "signed_flow", "F1_horizon_10", "horizon", sub(G, horizon_years=10)),
        ("extra", "signed_flow", "F1_horizon_30", "horizon", sub(G, horizon_years=30)),
        ("extra", "signed_flow", "F2_gamma8", "risk aversion", sub(G, preferences=sub(G.preferences, gamma=8.0))),
    ]
    for tier, kind, name, factor, spec in rows:   # fail fast on a bad override
        studies.spec_model(kind).model_validate(spec.model_dump())
    return rows


def frontier_headline(res):
    """Survival at the table cells, b_min and max sustainable r at 90/95%, CE-vs-survival optimum gap."""
    out = {}
    rs, bs = res["r"], res["b"]
    h = str(res.get("main_horizon", 30)) if str(res.get("main_horizon", 30)) in res["p_success"] else list(res["p_success"])[-1]
    P = res["p_success"][h]                        # [b][r]

    def near(xs, x):
        return min(range(len(xs)), key=lambda i: abs(xs[i] - x))
    for r in (0.03, 0.04, 0.045, 0.05):
        for b in (0.0, 0.2, 0.4, 0.6, 1.0):
            out["S_r%.1f_b%d" % (100 * r, round(100 * b))] = P[near(bs, b)][near(rs, r)]
    for s in ("0.90", "0.95"):
        rows = res["thresholds"].get("%s|%s" % (h, s), [])
        for r in (0.04, 0.045):
            row = rows[near([x["r"] for x in rows], r)] if rows else {}
            out["bmin_%s_r%.1f" % (s, 100 * r)] = row.get("b_min")
            out["bmin_status_%s_r%.1f" % (s, 100 * r)] = row.get("status")
        mx = res["max_sustainable"].get(s, [])
        best = max((x for x in mx if x["max_r"] is not None), key=lambda x: x["max_r"], default=None)
        out["max_r_%s" % s] = best["max_r"] if best else None
        out["argmax_b_%s" % s] = best["b"] if best else None
        out["breakpoint_%s" % s] = res.get("breakpoints", {}).get(s)
    out["max_ce_vs_survival_gap_pp"] = max((100 * o["distance"] for o in res.get("optima", [])), default=None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["must", "all"], default="must")
    ap.add_argument("--only", nargs="*", help="study kinds or ablation names to run")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    rows = [r for r in ablations() if a.tier == "all" or r[0] == "must"]
    if a.only:
        rows = [r for r in rows if r[1] in a.only or r[2] in a.only]
    if a.dry_run:
        for tier, kind, name, factor, _ in rows:
            print("%-6s %-18s %-24s %s" % (tier, kind, name, factor))
        print(len(rows), "specs validated")
        return
    from lifecycle.runs import executor, registry

    OUT.mkdir(parents=True, exist_ok=True)
    summary_path = OUT / "ablation_summary.csv"
    done = []
    for tier, kind, name, factor, spec in rows:
        t0 = time.time()
        print("running %s %s ..." % (kind, name), flush=True)
        rid = executor.run_sync(kind, spec, "ablation " + name)
        row = registry.get(rid) or {}
        res = registry.load_results(rid) if row.get("status") == "done" else None
        rec = {"study": kind, "ablation": name, "factor": factor, "run_id": rid, "status": row.get("status"),
               "seconds": round(time.time() - t0, 1), "error": (row.get("error") or "").split("\n")[0][:300]}
        if res is not None:
            rec.update(row.get("summary") or {})
            if kind == "frontier":
                rec.update(frontier_headline(res))
            (OUT / ("%s_%s.json" % (name, rid[:12]))).write_text(json.dumps(
                {"run_id": rid, "catalog_hash": row.get("catalog_hash"), "spec": row.get("spec"), "results": res},
                default=str))
        print("   ", rec["status"], rid, rec["error"], flush=True)
        done.append(rec)
        keys = sorted({k for d in done for k in d}, key=lambda k: (k not in ("study", "ablation", "factor", "run_id", "status"), k))
        with summary_path.open("w", newline="") as fh:   # rewrite after every run so a crash keeps what finished
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(done)
    print("wrote", summary_path)


if __name__ == "__main__":
    main()
```
