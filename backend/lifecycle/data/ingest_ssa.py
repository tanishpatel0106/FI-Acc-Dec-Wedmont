"""SSA Office of the Chief Actuary period life table (q_x by age and sex).

If the SSA page cannot be reached, a Gompertz fit to the 2019 SSA period table is
written instead and flagged provenance=model_generated so it is never mistaken for data.
"""
import io

import numpy as np
import pandas as pd

from lifecycle.config import processed_dir
from lifecycle.data.http import fetch

URL = "https://www.ssa.gov/oact/STATS/table4c6.html"

# Gompertz hazard mu(x) = B exp(c x), fitted to SSA 2019 period q_65 and q_85
GOMPERTZ = {"male": (5.9e-5, 0.0852), "female": (2.19e-5, 0.0933)}


def gompertz_table() -> pd.DataFrame:
    ages = np.arange(0, 120)
    out = {"age": ages}
    for sex, (b, c) in GOMPERTZ.items():
        mu = b * np.exp(c * ages)
        q = 1.0 - np.exp(-mu)
        q[-1] = 1.0
        out["q_" + sex] = np.minimum(q, 1.0)
    frame = pd.DataFrame(out)
    frame["q_unisex"] = 0.5 * (frame["q_male"] + frame["q_female"])
    frame["provenance"] = "model_generated"
    frame["source"] = "gompertz_fit:ssa_2019_period"
    return frame


def pull_ssa() -> pd.DataFrame:
    try:
        path = fetch(URL, "ssa_table4c6.html")
        tables = pd.read_html(io.StringIO(path.read_text(errors="replace")))
        table = None
        for t in tables:
            if t.shape[0] > 100 and t.shape[1] >= 7:
                table = t
                break
        if table is None:
            raise RuntimeError("no life table found in SSA page")
        table = table.iloc[:, :7]
        table.columns = ["age", "q_male", "n_male", "e_male", "q_female", "n_female", "e_female"]
        table = table.apply(pd.to_numeric, errors="coerce").dropna(subset=["age", "q_male", "q_female"])
        frame = pd.DataFrame({"age": table["age"].astype(int), "q_male": table["q_male"],
                              "q_female": table["q_female"]})
        frame["q_unisex"] = 0.5 * (frame["q_male"] + frame["q_female"])
        frame["provenance"] = "observed"
        frame["source"] = "ssa:oact.table4c6"
    except Exception as exc:
        print("warning: SSA life table unavailable (" + str(exc) + "); writing Gompertz fallback")
        frame = gompertz_table()
    frame.to_parquet(processed_dir() / "life_table.parquet", index=False)
    return frame


def load_life_table() -> pd.DataFrame:
    path = processed_dir() / "life_table.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return gompertz_table()
