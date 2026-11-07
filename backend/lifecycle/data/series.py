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
_add(SeriesDef("gold", "Gold (observed fund total return, e.g. GLD via WRDS CRSP)", "real_assets", "total_return",
               "decimal/month"))
_add(SeriesDef("gold_hist", "Gold historical price (research-only, rights-approved public source)", "real_assets",
               "price_return", "decimal/month"))
_add(SeriesDef("tbill", "T-bills (1M)", "cash", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_2y", "Treasury 2Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_5y", "Treasury 5Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_10y", "Treasury 10Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_20y", "Treasury 20Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ust_30y", "Treasury 30Y", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("tips", "TIPS", "rates", "total_return", "decimal/month", defensive=True))
_add(SeriesDef("ig_credit", "Investment-grade credit", "credit", "total_return", "decimal/month"))
_add(SeriesDef("hy_credit", "High-yield credit (observed fund total return, e.g. HYG via WRDS CRSP)", "credit",
               "total_return", "decimal/month"))
_add(SeriesDef("commodities", "Broad commodities (observed fund total return, e.g. DBC via WRDS CRSP)", "commodities",
               "total_return", "decimal/month"))
_add(SeriesDef("fx_basket", "Currencies: equal-weight GBP/JPY/CAD/AUD deposits for a USD investor", "currency",
               "total_return", "decimal/month"))
for _c in ["gbp", "jpy", "cad", "aud"]:
    _add(SeriesDef("fx_" + _c, _c.upper() + " overnight deposit (USD investor)", "currency", "total_return", "decimal/month"))
    _add(SeriesDef("fxs_" + _c, "USD per " + _c.upper() + " (month-end spot)", "state", "index_level", "level",
                   investable=False))
    _add(SeriesDef("y_cm_" + _c, _c.upper() + " call-money rate", "state", "yield", "decimal/year", investable=False))
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
    # v2 universes (brief 4.4): explicit, non-overlapping definitions; nothing is spliced or back-filled
    "core_long_history": UniverseDef(
        "core_long_history", "Long-history core (US equity, T-bills, 10Y Treasury)",
        required=("us_eq", "tbill", "ust_10y"),
    ),
    "core_duration": UniverseDef(
        "core_duration", "Duration ladder (US equity, cash, 2/5/10/30Y Treasuries)",
        required=("us_eq", "tbill", "ust_2y", "ust_5y", "ust_10y", "ust_30y"),
    ),
    "pp_modern_etf": UniverseDef(
        "pp_modern_etf", "Permanent Portfolio, implementable (equity, long Treasury, gold fund, T-bills)",
        required=("us_eq", "ust_30y", "gold", "tbill"),
        optional=("tips", "ust_10y", "ust_5y", "ust_2y"),
    ),
    "pp_research_historical": UniverseDef(
        "pp_research_historical", "Permanent Portfolio, long-history research proxy (approved gold price series)",
        required=("us_eq", "ust_30y", "gold_hist", "tbill"),
    ),
    "liability_match": UniverseDef(
        "liability_match", "Liability matching (equity, cash, TIPS, 2/5/10Y Treasuries)",
        required=("us_eq", "tbill", "tips", "ust_2y", "ust_5y", "ust_10y"),
    ),
    # multi-asset tiers: the public tier has long history; the full tier adds WRDS-only sleeves (gold,
    # commodities, high yield) and therefore starts when the youngest fund starts. They are never spliced.
    "multi_asset_public": UniverseDef(
        "multi_asset_public", "Multi-asset, public tier (US/intl/EM equity, 10Y and 30Y Treasury, IG credit, "
                              "currencies, T-bills)",
        required=("us_eq", "intl_eq", "em_eq", "ust_10y", "ust_30y", "ig_credit", "fx_basket", "tbill"),
    ),
    "multi_asset_full": UniverseDef(
        "multi_asset_full", "Multi-asset, full tier (public tier + TIPS, high yield, gold, commodities; WRDS)",
        required=("us_eq", "intl_eq", "em_eq", "ust_10y", "ust_30y", "tips", "ig_credit", "hy_credit", "gold",
                  "commodities", "fx_basket", "tbill"),
    ),
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
