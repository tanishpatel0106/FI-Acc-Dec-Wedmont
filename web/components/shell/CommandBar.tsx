"use client";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { PlaceholdersAndVanishInput } from "@/components/ui/placeholders-and-vanish-input";
import { useCatalog, useRuns } from "@/lib/api/hooks";
import { NAV } from "./AppShell";

/** Quick search over pages, series and runs. Enter jumps to the best match. */
export function CommandBar() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const runs = useRuns(undefined, 200);
  const cat = useCatalog();
  const items = useMemo(() => {
    const out: { label: string; href: string; kind: string }[] = NAV.map((n) => ({ label: n.label, href: n.href, kind: "page" }));
    for (const r of runs.data?.runs ?? []) {
      out.push({ label: (r.label ?? r.kind) + " " + r.run_id, href: "/runs?id=" + r.run_id, kind: r.kind });
    }
    for (const s of cat.data?.series ?? []) {
      out.push({ label: s.series_id + " " + s.label, href: "/lab?series=" + s.series_id, kind: "series" });
    }
    return out;
  }, [runs.data, cat.data]);
  const matches = q.trim() === "" ? [] : items.filter((i) => i.label.toLowerCase().includes(q.toLowerCase())).slice(0, 7);
  return (
    <div className="relative w-full max-w-md">
      <PlaceholdersAndVanishInput
        placeholders={["Search runs, series and pages…", "heatmap", "Treasury 10Y", "Policy optimizer", "run id…"]}
        onChange={(e) => setQ(e.target.value)}
        onSubmit={(e) => {
          e.preventDefault();
          if (matches.length > 0) router.push(matches[0].href);
          setQ("");
        }}
      />
      {matches.length > 0 ? (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 overflow-hidden rounded-lg border border-border bg-popover shadow-lg">
          {matches.map((m) => (
            <button key={m.href + m.label} onMouseDown={() => { router.push(m.href); setQ(""); }}
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-muted">
              <span className="truncate">{m.label}</span>
              <span className="ml-2 shrink-0 text-xs text-muted-foreground">{m.kind}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
