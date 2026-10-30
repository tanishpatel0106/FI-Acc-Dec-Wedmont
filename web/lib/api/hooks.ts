"use client";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "./client";
import type { ExperimentResults, RunRow, RunStatus, Surface } from "./types";

/* eslint-disable @typescript-eslint/no-explicit-any */
export function useCatalog() {
  return useQuery({ queryKey: ["catalog"], queryFn: () => apiGet<any>("/v1/catalog/series"), staleTime: 60_000 });
}

export function useOverview() {
  return useQuery({ queryKey: ["overview"], queryFn: () => apiGet<any>("/v1/overview"), refetchInterval: 15_000 });
}

export function useMarket(path: string, params: Record<string, string | number | undefined>) {
  return useQuery({
    queryKey: ["market", path, params],
    queryFn: () => apiGet<any>("/v1/market/" + path, params),
    staleTime: 5 * 60_000,
  });
}

export function useRunStatus(runId: string | null) {
  return useQuery({
    queryKey: ["status", runId],
    enabled: !!runId,
    queryFn: () => apiGet<RunStatus>("/v1/experiments/" + runId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "failed" || s === "cancelled" ? false : 1500;
    },
  });
}

export function useResults(runId: string | null, enabled = true) {
  return useQuery({
    queryKey: ["results", runId],
    enabled: !!runId && enabled,
    queryFn: () => apiGet<{ spec: any; kind: string; results: ExperimentResults }>("/v1/experiments/" + runId + "/results"),
    staleTime: Infinity,
    retry: false,
  });
}

export function useRuns(kind?: string, limit = 100) {
  return useQuery({
    queryKey: ["runs", kind, limit],
    queryFn: () => apiGet<{ runs: RunRow[] }>("/v1/experiments", { kind, limit }),
    refetchInterval: 10_000,
  });
}

export function useSweeps() {
  return useQuery({
    queryKey: ["sweeps"],
    queryFn: () => apiGet<{ sweeps: RunRow[] }>("/v1/sweeps"),
    refetchInterval: 10_000,
  });
}

export function useSurface(sweepId: string | null) {
  return useQuery({
    queryKey: ["surface", sweepId],
    enabled: !!sweepId,
    queryFn: () => apiGet<{ status: string; progress: number; stage: string; spec: any; surface?: Surface }>(
      "/v1/sweeps/" + sweepId + "/surface"),
    refetchInterval: (q) => (q.state.data?.status === "done" || q.state.data?.status === "failed" ? false : 3000),
  });
}

export function useJob(path: string | null, params?: Record<string, string | number | boolean>) {
  return useQuery({
    queryKey: ["job", path, params],
    enabled: !!path,
    queryFn: () => apiGet<any>(path as string, params),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "failed" || s === "none" || s === "cancelled" ? false : 3000;
    },
  });
}
