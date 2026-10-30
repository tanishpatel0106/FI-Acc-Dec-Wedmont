from fastapi import APIRouter

from lifecycle import analytics
from lifecycle.api.common import envelope
from lifecycle.data import panel
from lifecycle.data.series import UNIVERSES

router = APIRouter(prefix="/v1", tags=["catalog & market"])


@router.get("/catalog/series")
def catalog_series() -> dict:
    cat = panel.catalog()
    universes = {}
    for name in UNIVERSES:
        try:
            u = panel.universe_data(name)
            universes[name] = {"label": UNIVERSES[name].label, "assets": list(u.assets),
                               "labels": {a: panel.asset_label(a) for a in u.assets},
                               "window": [u.start.date().isoformat(), u.end.date().isoformat()],
                               "n_months": int(len(u.real)), "excluded": u.excluded,
                               "dropped_months": u.n_dropped_months}
        except Exception as exc:
            universes[name] = {"error": str(exc)}
    meta = panel.meta()
    return envelope({"series": cat.to_dict(orient="records"), "universes": universes, "as_of": panel.as_of(),
                     "built_at": meta.get("built_at"), "synthetic": bool(meta.get("synthetic", False)),
                     "sources": meta.get("choices", {}),
                     "wrds": any(str(s).startswith("wrds:") for s in cat["source"])})


@router.get("/market/returns/summary")
def returns_summary(universe: str = "core", start: str | None = None, end: str | None = None) -> dict:
    return envelope(analytics.returns_summary(universe, start, end))


@router.get("/market/dependence")
def market_dependence(universe: str = "core", a: str = "us_eq", b: str = "ust_10y", start: str | None = None,
                      end: str | None = None) -> dict:
    return envelope(analytics.dependence_view(universe, a, b, start, end))


@router.get("/market/yield-curve")
def yield_curve(date: str | None = None, withdrawal: float = 40_000.0, years: int = 30) -> dict:
    return envelope(analytics.yield_curve_view(date, withdrawal, years))


@router.get("/market/regimes")
def regimes(universe: str = "core", k: int = 2, start: str | None = None, end: str | None = None) -> dict:
    return envelope(analytics.regimes_view(universe, k, start, end))


@router.get("/market/factors")
def factors(universe: str = "core") -> dict:
    return envelope(analytics.factors_view(universe))
