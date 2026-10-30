"""Build every paper figure from stored run IDs only (research/experiments/run_ids.json).

Each figure caption carries the run ID and catalog hash, so every exhibit is traceable to a
reproducible run (`make reproduce RUN=<id>`).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from lifecycle.runs import registry  # noqa: E402

FIG = Path(__file__).with_name("figures")
FIG.mkdir(exist_ok=True)


def _caption(run_id: str) -> str:
    row = registry.get(run_id) or {}
    return "run %s, catalog %s, engine %s" % (run_id, row.get("catalog_hash"), row.get("engine_version"))


def heatmap(run_id: str, name: str, benchmark: str | None = None) -> None:
    res = registry.load_results(run_id)
    if res is None:
        print("missing results for", run_id)
        return
    b = benchmark or res["benchmarks"][0]
    m = np.array(res["matrices"][b]["delta"], dtype=float) * 100
    se = np.array(res["matrices"][b]["se"], dtype=float) * 100
    lim = max(np.nanmax(np.abs(m)), 0.5)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    im = ax.imshow(m, cmap="RdBu", vmin=-lim, vmax=lim, origin="lower", aspect="auto")
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            weak = abs(m[i, j]) < 2 * se[i, j]
            ax.text(j, i, "%+.1f" % m[i, j], ha="center", va="center", fontsize=7, color="0.4" if weak else "black")
    ax.set_xticks(range(len(res["x"])), ["%.1f%%" % (100 * v) for v in res["x"]], rotation=45, fontsize=8)
    ax.set_yticks(range(len(res["y"])), [str(v) for v in res["y"]], fontsize=8)
    ax.set_xlabel(res["x_label"])
    ax.set_ylabel(res["y_label"])
    fig.colorbar(im, label="ΔCE (%) vs " + b)
    fig.text(0.01, 0.01, _caption(run_id), fontsize=6, color="0.4")
    fig.tight_layout()
    fig.savefig(FIG / (name + ".pdf"))
    fig.savefig(FIG / (name + ".png"), dpi=160)
    plt.close(fig)
    print("wrote", name)


def transition(run_id: str, name: str) -> None:
    res = registry.load_results(run_id)
    if res is None or "surfaces" not in res:
        return
    s = res["surfaces"]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for row in s["by_regime"][0]:
        ax.plot(row["q"], row["equity"], label="age %g" % row["age"])
    ax.set_xlim(-1, 1)
    ax.set_xlabel("q = (c - y) / x")
    ax.set_ylabel("optimal equity weight")
    ax.legend(fontsize=7, ncol=3)
    fig.text(0.01, 0.01, _caption(run_id), fontsize=6, color="0.4")
    fig.tight_layout()
    fig.savefig(FIG / (name + ".pdf"))
    plt.close(fig)
    print("wrote", name)


def shapley(run_id: str, name: str) -> None:
    res = registry.load_results(run_id)
    if res is None:
        return
    fig, ax = plt.subplots(figsize=(7, 4.2))
    k = len(res["conditions"])
    w = 0.8 / k
    x = np.arange(len(res["sleeves"]))
    for i, c in enumerate(res["conditions"]):
        ax.bar(x + i * w, [c["shapley"][s] for s in res["sleeves"]], w, label=c["condition"])
    ax.set_xticks(x + 0.4 - w / 2, res["sleeves"])
    ax.set_ylabel("Shapley MU ($/yr)")
    ax.legend(fontsize=7)
    fig.text(0.01, 0.01, _caption(run_id), fontsize=6, color="0.4")
    fig.tight_layout()
    fig.savefig(FIG / (name + ".pdf"))
    plt.close(fig)
    print("wrote", name)


def main() -> None:
    ids_path = ROOT / "research" / "experiments" / "run_ids.json"
    if not ids_path.exists():
        sys.exit("run `make seed` first: research/experiments/run_ids.json not found")
    ids = json.loads(ids_path.read_text())
    if "01_decumulation_core_bootstrap" in ids:
        heatmap(ids["01_decumulation_core_bootstrap"], "fig1_decumulation_heatmap")
    if "02_accumulation_core_bootstrap" in ids:
        heatmap(ids["02_accumulation_core_bootstrap"], "fig2_accumulation_heatmap")
    if "12_dp_markov_switching" in ids:
        transition(ids["12_dp_markov_switching"], "fig3_transition")
    for r in registry.list_runs("attribution", 5):
        if r["status"] == "done":
            shapley(r["run_id"], "fig4_shapley_by_regime")
            break


if __name__ == "__main__":
    main()
