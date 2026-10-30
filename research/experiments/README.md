# Versioned exhibit specifications

Every paper exhibit and every headline number in the app is produced from one of these files.

- `kind`: `experiment` | `sweep` | `attribution` | `hypotheses`
- `tier`: `core` (run by `make seed`) or `full` (run by `make seed-full`)
- `spec`: the exact `ExperimentSpec` / `SweepSpec` posted to the API

Run IDs are the SHA-256 of the canonical spec (plus the data catalog hash), so re-running a file on the
same data returns the cached run. `make seed` writes the resulting IDs to `run_ids.json`, which
`make paper` reads to build figures.
