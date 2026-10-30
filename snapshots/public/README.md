# Public-data snapshot

A committed copy of every **public** source the platform uses, so the panel can be built with no
network access:

```bash
make data-offline                 # public panel from this snapshot
make ingest-wrds OFFLINE=1        # WRDS (live, Duo push) + public data from this snapshot
make snapshot                     # refresh this folder from the live sources
```

| File | Source | Content |
| --- | --- | --- |
| `fred.parquet` | FRED (St. Louis Fed) | CPI NSA/SA, CMT yields 2/5/10/20/30Y, TIPS 5/10Y, breakevens, 3M bill, Moody's Aaa/Baa, unemployment, industrial production, NBER recessions, VIX |
| `french.parquet` | Kenneth French Data Library | US market and RF (1926-), FF3/FF5 + momentum, developed ex-US and emerging markets |
| `gsw.parquet` | Federal Reserve (Gürkaynak–Sack–Wright) | month-end nominal (1–30Y) and TIPS real (2–20Y) zero-coupon yields |
| `acm.parquet` | NY Fed | ACM 10Y term premium and expected short rate |
| `life_table.parquet` | SSA period life table, or a Gompertz fit flagged `model_generated` if SSA was unreachable | q_x by age and sex |

Each file holds canonical panel rows (`month_end, series_id, value, quantity, provenance, source,
vintage, available_from`). `manifest.json` records the vintage, coverage, row counts and SHA-256 of
every file; `load_snapshot` refuses a file whose hash no longer matches. Only complete months are
included. Building from the snapshot gives the same catalog hash as a live pull made on the same day,
so run IDs are identical.

WRDS data is never snapshotted or committed. A few FRED series are third-party data redistributed by
FRED (Moody's Aaa/Baa yields, CBOE VIX); keep the repository private if you share it outside the team.
