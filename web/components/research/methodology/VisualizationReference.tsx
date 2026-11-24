"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { PAGES } from "@/lib/research/routes";
import { VISUALIZATIONS, vizHref } from "@/lib/research/visualization-registry";

/**
 * The reference entry of every registered visualization, grouped by page and section. Generated from the
 * same registry that drives the information panels, so the two can never disagree.
 */
export function VisualizationReference() {
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? VISUALIZATIONS.filter((v) => (v.id + " " + v.title + " " + v.researchQuestion + " " + v.plainEnglishExplanation).toLowerCase().includes(s)) : VISUALIZATIONS;
  }, [q]);
  return (
    <div className="space-y-6" data-testid="viz-reference">
      <div className="flex flex-wrap items-center gap-3">
        <input aria-label="Filter visualizations" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by ID, title or question…"
          className="h-8 w-72 rounded border border-input bg-transparent px-2 text-sm" />
        <span className="text-xs text-muted-foreground">{list.length} of {VISUALIZATIONS.length} visualizations · source: web/lib/research/visualization-registry.ts</span>
      </div>
      {PAGES.map((p) => {
        const items = list.filter((v) => v.page === p.key);
        if (!items.length) return null;
        return (
          <section key={p.key} aria-labelledby={"ref-page-" + p.key}>
            <h3 id={"ref-page-" + p.key} className="mb-2 text-sm font-semibold">{p.name} <span className="font-normal text-muted-foreground">({items.length})</span></h3>
            <div className="grid gap-2 lg:grid-cols-2">
              {items.map((v) => (
                <article key={v.id} id={"ref-" + v.id} className="scroll-mt-24 rounded-lg border border-border p-3 text-xs">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div><span className="mr-2 font-mono text-muted-foreground">{v.id}</span><span className="font-medium">{v.title}</span></div>
                    <Link className="underline" href={vizHref(v.id)}>Open chart →</Link>
                  </div>
                  <p className="mt-1 text-muted-foreground">{v.researchQuestion}</p>
                  <p className="mt-1">{v.plainEnglishExplanation}</p>
                  <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-2 text-[11px]">
                    {v.axes.x ? <><dt className="text-muted-foreground">x</dt><dd>{v.axes.x}</dd></> : null}
                    {v.axes.y ? <><dt className="text-muted-foreground">y</dt><dd>{v.axes.y}</dd></> : null}
                    <dt className="text-muted-foreground">units</dt><dd>{v.units}</dd>
                    <dt className="text-muted-foreground">method</dt><dd>{v.calculationMethod}</dd>
                    <dt className="text-muted-foreground">needs</dt><dd>{v.dataRequirements}</dd>
                  </dl>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
