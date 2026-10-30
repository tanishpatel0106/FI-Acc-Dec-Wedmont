"""Canonical series definitions and the two research universes (brief 3.3)."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SeriesDef:
    series_id: str
    label: str
    asset_class: str          # equity, rates, cash, credit, real_assets, inflation, state, factor
    quantity: str
    units: str
    investable: bool = True
    defensive: bool = False   # eligible for the safe sleeve of parametric policies


SERIES: dict[str, SeriesDef] = {}


def _add(s: SeriesDef) -> None:
    SERIES[s.series_id] = s


_add(SeriesDef("us_eq", "US equity (value-weighted)", "equity", "total_return", "decimal/month"))
_add(SeriesDef("intl_eq", "Developed ex-US equity", "equity", "total_return", "decimal/month"))
_add(SeriesDef("em_eq", "Emerging-market equity", "equity", "total_return", "decimal/month"))
_add(SeriesDef("reit", "Listed REITs", "real_assets", "total_return", "decimal/month"))
_add(SeriesDef("gold", "Gold", "real_assets", "total_return", "decimal/month"))
_add(SeriesDef("tbill", "T-bills (1M)", "cash", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_2y", "Treasury 2Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_5y", "Treasury 5Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_10y", "Treasury 10Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_20y", "Treasury 20Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_30y", "Treasury 30Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("tips", "TIPS", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ig_credit", "Investment-grade credit", "credit", "total_return", "decimal/month"))
_add(SeriesDef("hy_credit", "High-yield credit", "credit", "total_return", "decimal/month"))
_add(SeriesDef("cpi_nsa", "CPI-U NSA inflation", "inflation", "rate", "decimal/month", investable=False))
_add(SeriesDef("cpi_sa", "CPI-U SA inflation", "inflation", "rate", "decimal/month", investable=False))

for _f in ["mktrf", "smb", "hml", "rmw", "cma", "umd", "rf"]:
    _add(SeriesDef("ff_" + _f, "Fama-French " + _f.upper(), "factor", "total_return", "decimal/month",
                   investable=False))

for _k, _lab in [("dgs2", "2Y CMT yield"), ("dgs5", "5Y CMT yield"), ("dgs10", "10Y CMT yield"),
                 ("dgs30", "30Y CMT yield"), ("dfii5", "5Y TIPS yield"), ("dfii10", "10Y TIPS yield"),
                 ("t5yie", "5Y breakeven"), ("t10yie", "10Y breakeven"), ("tb3ms", "3M bill rate"),
                 ("aaa", "Moody's Aaa yield"), ("baa", "Moody's Baa yield")]:
    _add(SeriesDef("y_" + _k, _lab, "state", "yield", "decimal/year", investable=False))
for _k, _lab, _q in [("unrate", "Unemployment rate", "rate"), ("indpro", "Industrial production", "index_level"),
                     ("usrec", "NBER recession (retrospective only)", "rate"),
                     ("vixcls", "VIX", "index_level"), ("acm_tp10", "ACM 10Y term premium", "yield"),
                     ("acm_rny10", "ACM 10Y expected short rate", "yield")]:
    _add(SeriesDef("s_" + _k, _lab, "state", _q, "level", investable=False))
for _m in range(1, 31):
    _add(SeriesDef("gsw_nom_%02d" % _m, "GSW nominal zero yield %dY" % _m, "state", "yield", "decimal/year",
                   investable=False))
for _m in range(2, 21):
    _add(SeriesDef("gsw_real_%02d" % _m, "GSW TIPS real zero yield %dY" % _m, "state", "yield", "decimal/year",
                   investable=False))


@dataclass(frozen=True)
class UniverseDef:
    name: str
    label: str
    required: tuple[str, ...]
    optional: tuple[str, ...] = field(default_factory=tuple)
    inflation: str = "cpi_nsa"


UNIVERSES: dict[str, UniverseDef] = {
    "core": UniverseDef(
        "core", "Long-history core",
        required=("us_eq", "tbill", "ust_10y"),
        optional=("ust_2y", "ust_5y", "ust_20y"),
    ),
    "modern": UniverseDef(
        "modern", "Modern diversified",
        required=("us_eq", "tbill", "ust_10y", "intl_eq", "em_eq", "ig_credit", "tips"),
        optional=("reit", "ust_2y", "ust_5y", "ust_30y", "gold"),
    ),
}

# optional series join the universe only if they start within this many months of the required window
OPTIONAL_TOLERANCE_MONTHS = 0
