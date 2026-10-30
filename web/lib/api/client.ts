import type { components } from "./schema";

export type ExperimentSpec = components["schemas"]["ExperimentSpec"];
export type SweepSpec = components["schemas"]["SweepSpec"];
export type CompareSpec = components["schemas"]["CompareSpec"];

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

export interface Envelope {
  run_id: string | null;
  spec_hash: string | null;
  catalog_hash: string | null;
  engine_version: string;
  generated_at: string;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, title: string, detail: string) {
    super(title + (detail ? ": " + detail : ""));
    this.status = status;
    this.detail = detail;
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let title = res.statusText;
    let detail = "";
    try {
      const body = await res.json();
      title = body.title ?? title;
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, title, detail);
  }
  return (await res.json()) as T;
}

export async function apiGet<T>(path: string, params?: Record<string, string | number | boolean | null | undefined>): Promise<T & Envelope> {
  const url = new URL(API_BASE + path);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString(), { cache: "no-store" });
  return handle<T & Envelope>(res);
}

export async function apiPost<T>(path: string, body: unknown, params?: Record<string, string>): Promise<T & Envelope> {
  const url = new URL(API_BASE + path);
  if (params) for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handle<T & Envelope>(res);
}

export function eventsUrl(runId: string): string {
  return API_BASE + "/v1/experiments/" + runId + "/events";
}

export function reportUrl(runId: string, format: "pdf" | "csv" | "bibtex" | "json"): string {
  return API_BASE + "/v1/reports/" + runId + "?format=" + format;
}

export async function fetchArrow(path: string): Promise<ArrayBuffer> {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new ApiError(res.status, res.statusText, "");
  return res.arrayBuffer();
}
