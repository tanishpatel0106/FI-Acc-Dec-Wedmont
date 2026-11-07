"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { API_BASE, apiGet, apiPost } from "./client";

/* eslint-disable @typescript-eslint/no-explicit-any */
export type StudyKind =
  | "frontier" | "signed_flow" | "permanent" | "rebalance" | "scenario_lab" | "asof" | "optimize" | "compare_v2" | "evidence" | "multi_asset" | "historical_replay";

export interface StudyEnvelope {
  status: "none" | "queued" | "running" | "done" | "failed" | "cancelled";
  stage?: string;
  progress?: number;
  kind: string;
  error?: string | null;
  spec?: any;
  results?: any;
  created_at?: string;
  finished_at?: string | null;
  page?: string;
  experiments?: string;
  run_id: string | null;
  spec_hash: string | null;
  catalog_hash: string | null;
  engine_version: string;
  generated_at: string;
}

const terminal = (s?: string) => s === "done" || s === "failed" || s === "cancelled" || s === "none";

/** Latest completed run of a study kind (lookup only: never launches computation). */
export function useStudyLatest(kind: StudyKind, enabled = true) {
  return useQuery({
    queryKey: ["study-latest", kind],
    enabled,
    queryFn: () => apiGet<StudyEnvelope>("/v1/studies/" + kind + "/latest"),
    refetchInterval: (q) => (terminal(q.state.data?.status) ? false : 2500),
    staleTime: 10_000,
  });
}

export function useStudyRun(runId: string | null) {
  return useQuery({
    queryKey: ["study-run", runId],
    enabled: !!runId,
    queryFn: () => apiGet<StudyEnvelope>("/v1/studies/run/" + runId),
    refetchInterval: (q) => (terminal(q.state.data?.status) ? false : 2500),
  });
}

export async function submitStudy(kind: StudyKind, spec: any, force = false): Promise<StudyEnvelope> {
  return apiPost<StudyEnvelope>("/v1/studies/" + kind, spec ?? {}, force ? { force: "true" } : undefined);
}

export function useStudyDefaults(kind: StudyKind) {
  return useQuery({ queryKey: ["study-defaults", kind], queryFn: () => apiGet<any>("/v1/studies/" + kind + "/defaults"),
    staleTime: Infinity });
}

export function useTrace(runId: string | null | undefined, params: Record<string, string | number | undefined>, enabled = true) {
  return useQuery({
    queryKey: ["trace", runId, params],
    enabled: !!runId && enabled,
    queryFn: () => apiGet<any>("/v1/studies/run/" + runId + "/trace", params),
    staleTime: Infinity,
    retry: false,
  });
}

export function useV2<T = any>(path: string | null, params?: Record<string, string | number | boolean | undefined>,
  opts?: { refetch?: number; staleTime?: number }) {
  return useQuery({
    queryKey: ["v2", path, params],
    enabled: !!path,
    queryFn: () => apiGet<T>(path as string, params),
    staleTime: opts?.staleTime ?? 60_000,
    refetchInterval: opts?.refetch,
  });
}

export function useInvalidateStudy() {
  const qc = useQueryClient();
  return (kind: StudyKind) => {
    void qc.invalidateQueries({ queryKey: ["study-latest", kind] });
  };
}

export function exportUrl(runId: string, format: "json" | "csv", block?: string) {
  return API_BASE + "/v1/studies/run/" + runId + "/export?format=" + format + (block ? "&block=" + encodeURIComponent(block) : "");
}

export { API_BASE };
