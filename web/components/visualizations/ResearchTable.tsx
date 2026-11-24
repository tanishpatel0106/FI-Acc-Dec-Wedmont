"use client";
import { useState, useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

/* eslint-disable @typescript-eslint/no-explicit-any */
const noopSubscribe = () => () => undefined;
function useMounted() {
  return useSyncExternalStore(noopSubscribe, () => true, () => false);
}

function fmtCell(v: any): React.ReactNode {
  if (v === null || v === undefined) return "–";
  if (typeof v === "number") return Number.isInteger(v) || Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : v.toFixed(4);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

/** Sortable research table. Rows come from client-side queries, so they render after hydration only. */
export function DataTable({ columns, rows, className }: { columns: { key: string; label: string; fmt?: (v: any, r: any) => React.ReactNode }[];
  rows: any[]; className?: string }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const mounted = useMounted();
  const data = mounted ? rows : [];
  const sorted = sort ? [...data].sort((a, b) => {
    const x = a[sort.key], y = b[sort.key];
    if (x === y) return 0;
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * sort.dir;
  }) : data;
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-xs tabular-nums">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            {columns.map((c) => (
              <th key={c.key} scope="col" aria-sort={sort?.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className="whitespace-nowrap px-2 py-1.5 font-medium">
                <button className="hover:text-foreground" onClick={() => setSort({ key: c.key, dir: sort?.key === c.key && sort.dir === 1 ? -1 : 1 })}>
                  {c.label}{sort?.key === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={i} className="border-b border-border/50 hover:bg-muted/40">
              {columns.map((c) => <td key={c.key} className="whitespace-nowrap px-2 py-1">{c.fmt ? c.fmt(r[c.key], r) : fmtCell(r[c.key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const ResearchTable = DataTable;
