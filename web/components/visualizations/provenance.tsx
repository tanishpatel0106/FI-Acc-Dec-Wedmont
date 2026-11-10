"use client";
import { createContext, useContext } from "react";

/** Dynamic provenance of the data behind the charts in a subtree (set by StudyGate or a page). */
export interface Provenance {
  runId?: string | null;
  catalogHash?: string | null;
  universe?: string | null;
  window?: string[] | null;
  generator?: string | null;
  nPaths?: number | null;
  horizon?: string | null;
  benchmark?: string | null;
  withdrawal?: number | null;
  finishedAt?: string | null;
  engineVersion?: string | null;
  asOf?: string | null;
  source?: string | null;
  dataClass?: "observed" | "model_generated" | "illustrative" | "unavailable";
  warnings?: string[];
}

const Ctx = createContext<Provenance>({});

export function ProvenanceProvider({ value, children }: { value: Provenance; children: React.ReactNode }) {
  const parent = useContext(Ctx);
  return <Ctx.Provider value={{ ...parent, ...value }}>{children}</Ctx.Provider>;
}

export function useProvenance(): Provenance {
  return useContext(Ctx);
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export function provenanceFromStudy(env: any): Provenance {
  const r = env?.results ?? {};
  const spec = env?.spec ?? {};
  const uni = r.universe ?? {};
  const horizon = spec?.investor?.horizon_years ?? r.main_horizon;
  return {
    runId: env?.run_id, catalogHash: env?.catalog_hash, universe: uni.name ?? spec?.data?.universe, window: uni.window,
    generator: r.scenario?.generator ?? spec?.scenario?.generator, nPaths: r.n_paths ?? spec?.scenario?.n_paths,
    horizon: horizon ? horizon + " years" : null, benchmark: r.benchmark ?? r.baseline ?? null,
    withdrawal: typeof r.withdrawal === "number" ? r.withdrawal : typeof spec?.withdrawal === "number" ? spec.withdrawal : null,
    finishedAt: env?.finished_at, engineVersion: env?.engine_version, asOf: r.as_of ?? null,
    source: "study " + (env?.kind ?? ""), dataClass: uni.data_class === "observed" ? "observed"
      : (r.warnings ?? []).some((w: string) => w.includes("SYNTHETIC")) ? "illustrative" : "model_generated",
    warnings: r.warnings ?? [],
  };
}
