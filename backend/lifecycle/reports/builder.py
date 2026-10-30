"""Export bundles for a run: PDF summary, CSV of key series, BibTeX (methods + run citation), JSON."""
import csv
import io
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from lifecycle.runs import registry  # noqa: E402

REFS = Path(__file__).with_name("references.bib")
DISCLAIMER = ("Research output only - not investment advice. Results are model-dependent; every figure is "
              "reproducible from the run ID and catalog hash shown.")


def bibtex(run_id: str) -> str:
    row = registry.get(run_id) or {}
    entry = ("@misc{lifecycle_run_" + run_id + ",\n"
             "  title  = {LIFECYCLE research run " + run_id + "},\n"
             "  note   = {kind=" + str(row.get("kind")) + "; spec_hash=" + str(row.get("spec_hash")) +
             "; catalog_hash=" + str(row.get("catalog_hash")) + "; engine=" + str(row.get("engine_version")) + "},\n"
             "  year   = {" + str(row.get("created_at", ""))[:4] + "}\n}\n\n")
    return entry + REFS.read_text()


def csv_bundle(run_id: str) -> str:
    res = registry.load_results(run_id) or {}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["run_id", run_id])
    if "matrices" in res:
        w.writerow(["benchmark", "y", "x", "delta_ce", "se", "p_depletion", "cell_run_id"])
        for b, m in res["matrices"].items():
            for i, y in enumerate(res["y"]):
                for j, x in enumerate(res["x"]):
                    w.writerow([b, y, x, m["delta"][i][j], m["se"][i][j], res["shortfall"][i][j],
                                res["cells"][i][j]["run_id"]])
        return buf.getvalue()
    ce = res.get("ce", {})
    for k, v in ce.items():
        if isinstance(v, dict):
            for kk, vv in v.items():
                w.writerow(["ce", k, kk, vv])
    fan = res.get("fan", {})
    ages = res.get("ages", [])
    for series, qs in fan.items():
        for q, vals in qs.items():
            w.writerow([series, q] + list(vals))
    if ages:
        w.writerow(["ages"] + ages)
    return buf.getvalue()


def pdf_bundle(run_id: str) -> bytes:
    row = registry.get(run_id) or {}
    res = registry.load_results(run_id) or {}
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.08, 0.95, "LIFECYCLE - run report", fontsize=18, weight="bold")
        lines = ["run_id: " + run_id, "kind: " + str(row.get("kind")), "spec_hash: " + str(row.get("spec_hash")),
                 "catalog_hash: " + str(row.get("catalog_hash")), "engine_version: " + str(row.get("engine_version")),
                 "created: " + str(row.get("created_at")), ""]
        ce = res.get("ce", {})
        if "policy" in ce:
            lines.append("Policy: %s" % res.get("policy", {}).get("label"))
            lines.append("CE consumption: $%.0f / yr (SE %.0f)" % (ce["policy"]["ce"], ce["policy"]["se"]))
        if "benchmark" in ce:
            lines.append("Benchmark (%s): $%.0f / yr" % (res.get("benchmark", {}).get("label", ""),
                                                         ce["benchmark"]["ce"]))
        if "delta" in ce:
            lines.append("Delta CE: %.2f%% +/- %.2f%% (paired SE)" % (100 * ce["delta"]["delta"],
                                                                     100 * ce["delta"]["se"]))
        sf = res.get("shortfall")
        if sf:
            lines.append("P(depletion): %.1f%%   mean normalised shortfall: %.3f" % (100 * sf["p_depletion"],
                                                                                    sf["mean_L"]))
        if "summary" in res and isinstance(res["summary"], dict):
            for k, v in res["summary"].items():
                lines.append("%s: %s" % (k, v))
        for w in res.get("warnings", []):
            lines.append("warning: " + str(w))
        lines += ["", DISCLAIMER]
        fig.text(0.08, 0.90, "\n".join(lines), fontsize=9, va="top", family="monospace", wrap=True)
        pdf.savefig(fig)
        plt.close(fig)
        if "fan" in res and "ages" in res and "wealth" in res["fan"]:
            fig, axes = plt.subplots(2, 1, figsize=(8.27, 11.69))
            ages = res["ages"]
            for ax, key, title in [(axes[0], "wealth", "Real wealth"), (axes[1], "consumption", "Real consumption")]:
                q = res["fan"][key]
                x = ages[: len(q["p50"])]
                ax.fill_between(x, q["p05"], q["p95"], alpha=0.2, label="5-95%")
                ax.fill_between(x, q["p25"], q["p75"], alpha=0.35, label="25-75%")
                ax.plot(x, q["p50"], lw=2, label="median")
                bkey = "benchmark_" + key
                if bkey in res["fan"]:
                    ax.plot(x, res["fan"][bkey]["p50"][: len(x)], "--", label="benchmark median")
                ax.set_title(title)
                ax.set_xlabel("age")
                ax.legend()
            pdf.savefig(fig)
            plt.close(fig)
        if "matrices" in res:
            import numpy as np

            b = res["benchmarks"][0]
            m = np.array(res["matrices"][b]["delta"], dtype=float) * 100
            fig, ax = plt.subplots(figsize=(8.27, 6))
            lim = np.nanmax(np.abs(m)) if np.isfinite(m).any() else 1
            im = ax.imshow(m, cmap="RdBu", vmin=-lim, vmax=lim, aspect="auto", origin="lower")
            ax.set_xticks(range(len(res["x"])), [str(v) for v in res["x"]], rotation=45)
            ax.set_yticks(range(len(res["y"])), [str(v) for v in res["y"]])
            ax.set_xlabel(res["x_label"])
            ax.set_ylabel(res["y_label"])
            ax.set_title("Delta CE (%) vs " + b)
            fig.colorbar(im)
            pdf.savefig(fig)
            plt.close(fig)
    return buf.getvalue()


def bundle(run_id: str, fmt: str) -> tuple[bytes, str, str]:
    if fmt == "pdf":
        return pdf_bundle(run_id), "application/pdf", run_id + ".pdf"
    if fmt == "csv":
        return csv_bundle(run_id).encode(), "text/csv", run_id + ".csv"
    if fmt == "bibtex":
        return bibtex(run_id).encode(), "application/x-bibtex", run_id + ".bib"
    if fmt == "json":
        import json

        payload: dict[str, Any] = {"run": registry.get(run_id), "results": registry.load_results(run_id)}
        return json.dumps(payload, default=str).encode(), "application/json", run_id + ".json"
    raise ValueError("unknown format: " + fmt)
