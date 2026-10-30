"""Combine raw vintages into the canonical panel: one source per series, chosen by priority.

Priority: WRDS observed > WRDS index-derived > public observed > public index-derived >
model-generated. Series are never spliced across sources.
"""
import json
from datetime import date

import pandas as pd

from lifecycle.config import processed_dir, raw_dir
from lifecycle.data.catalog import build_catalog, catalog_hash
from lifecycle.data.public_models import build_public_models
from lifecycle.data.schema import PANEL_COLUMNS, PROVENANCE_RANK

# if the canonical id is absent from every source, accept these stand-ins (recorded in the catalog)
ALIASES = {"ig_credit": ["ig_credit_etf"]}


def raw_store_path(group: str, name: str) -> str:
    folder = raw_dir() / group / date.today().isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder / (name + ".parquet"))


def write_raw(frame: pd.DataFrame, group: str, name: str) -> str:
    path = raw_store_path(group, name)
    frame.to_parquet(path, index=False)
    return path


def _latest_raw_frames() -> list[pd.DataFrame]:
    frames = []
    root = raw_dir()
    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue
        latest: dict[str, str] = {}
        for vintage_dir in sorted(group_dir.iterdir()):
            if not vintage_dir.is_dir():
                continue
            for f in vintage_dir.glob("*.parquet"):
                latest[f.name] = str(f)  # later vintages overwrite earlier ones
        for path in latest.values():
            frames.append(pd.read_parquet(path))
    return frames


def _rank(source: str, provenance: str) -> int:
    base = 0 if source.startswith("wrds:") else 10
    return base + PROVENANCE_RANK.get(provenance, 9)


def build_panel() -> dict:
    frames = _latest_raw_frames()
    if len(frames) == 0:
        raise RuntimeError("no raw data found; run `make data` (public) or `make ingest-wrds`")
    allrows = pd.concat(frames, ignore_index=True)
    allrows["month_end"] = pd.to_datetime(allrows["month_end"])
    models = build_public_models(allrows)
    if len(models) > 0:
        allrows = pd.concat([allrows, models], ignore_index=True)
    allrows = allrows.drop_duplicates(subset=["month_end", "series_id", "source"], keep="last")

    chosen = []
    choice_log = {}
    for sid, grp in allrows.groupby("series_id", sort=True):
        options = []
        for source, sgrp in grp.groupby("source"):
            options.append((_rank(str(source), str(sgrp["provenance"].iloc[0])), -len(sgrp), str(source)))
        options.sort()
        best = options[0][2]
        chosen.append(grp[grp["source"] == best])
        choice_log[sid] = {"chosen": best, "alternatives": [o[2] for o in options[1:]]}
    resolved = pd.concat(chosen, ignore_index=True)

    present = set(resolved["series_id"].unique())
    for canonical, alts in ALIASES.items():
        if canonical in present:
            continue
        for alt in alts:
            if alt in present:
                extra = resolved[resolved["series_id"] == alt].copy()
                extra["series_id"] = canonical
                resolved = pd.concat([resolved, extra], ignore_index=True)
                choice_log[canonical] = {"chosen": "alias:" + alt, "alternatives": []}
                break

    resolved = resolved[PANEL_COLUMNS].sort_values(["series_id", "month_end"]).reset_index(drop=True)
    catalog = build_catalog(resolved)
    chash = catalog_hash(catalog)
    out = processed_dir()
    resolved.to_parquet(out / "panel.parquet", index=False)
    allrows[PANEL_COLUMNS].to_parquet(out / "panel_all_sources.parquet", index=False)
    catalog.to_parquet(out / "series_catalog.parquet", index=False)
    meta = {"catalog_hash": chash, "built_at": pd.Timestamp.now().isoformat(), "choices": choice_log,
            "n_series": int(catalog.shape[0]), "n_rows": int(resolved.shape[0])}
    (out / "panel_meta.json").write_text(json.dumps(meta, indent=2))
    return meta
