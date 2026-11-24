"use client";
import Link from "next/link";
import { Fragment } from "react";
import { IconInfoCircle } from "@tabler/icons-react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tex } from "@/components/common/Tex";
import { VIZ_BY_ID, vizHref, type VizEntry } from "@/lib/research/visualization-registry";
import { shortId } from "@/lib/format";
import type { Provenance } from "./provenance";

const CLASS_TEXT = {
  observed: "Observed data", model_generated: "Model-generated (simulated or repriced)", illustrative: "Illustrative (synthetic)",
  unavailable: "Unavailable",
} as const;

function Block({ letter, title, children }: { letter: string; title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"><span className="mr-1 font-mono">{letter}.</span>{title}</h4>
      <div className="text-[13px] leading-relaxed">{children}</div>
    </section>
  );
}

/**
 * The information button every visualization carries. Opens an accessible side panel (Base UI dialog:
 * focus trap, Escape to close, labelled) with the registry explanation plus the live provenance.
 */
export function VisualizationInfo({ id, title, entry, prov, note, selection }: {
  id: string; title: string; entry?: VizEntry; prov: Provenance; note?: React.ReactNode; selection?: Record<string, string | number | null | undefined>;
}) {
  const e = entry;
  const sel = Object.entries(selection ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return (
    <Sheet>
      <SheetTrigger aria-label={"About this chart: " + title} data-viz-info={id}
        className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">
        <IconInfoCircle className="h-4 w-4" />
      </SheetTrigger>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl" aria-describedby={id + "-info-desc"}>
        <SheetHeader>
          <div className="font-mono text-[10px] text-muted-foreground">{id}</div>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription id={id + "-info-desc"}>{e?.researchQuestion ?? "No registry entry"}</SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4 pb-8" data-viz-info-body={id}>
          {!e ? (
            <div role="alert" className="rounded border border-destructive/50 p-3 text-xs text-destructive">
              Missing explanation: no entry for <code>{id}</code> in <code>web/lib/research/visualization-registry.ts</code>. The coverage test fails until it is added.
            </div>
          ) : (
            <>
              <Block letter="A" title="What this graph shows">{e.plainEnglishExplanation}</Block>
              <Block letter="B" title="How to read it">
                <ul className="list-disc space-y-0.5 pl-5">
                  {e.axes.x ? <li><b>X-axis:</b> {e.axes.x}</li> : null}
                  {e.axes.y ? <li><b>Y-axis:</b> {e.axes.y}</li> : null}
                  {e.axes.color ? <li><b>Colour:</b> {e.axes.color}</li> : null}
                  {e.axes.other ? <li><b>Layout:</b> {e.axes.other}</li> : null}
                  <li><b>Units:</b> {e.units}</li>
                  <li><b>Series, bands and markers:</b> {e.seriesMeaning}</li>
                </ul>
              </Block>
              <Block letter="C" title="What is being calculated">
                <p>{e.calculationMethod}</p>
                {e.formula ? <Tex block>{e.formula}</Tex> : null}
              </Block>
              <Block letter="D" title="Why it matters">{e.whyItMatters}</Block>
              <Block letter="E" title="How to interpret the result">{e.howToInterpret}</Block>
              <Block letter="F" title="Assumptions and limitations">
                <ul className="list-disc space-y-0.5 pl-5">
                  {e.assumptions.map((a) => <li key={a}>{a}</li>)}
                  {e.limitations.map((l) => <li key={l} className="text-muted-foreground">{l}</li>)}
                  {(prov.warnings ?? []).map((w) => <li key={w} className="text-[var(--viz-s4)]">This run: {w}</li>)}
                </ul>
              </Block>
            </>
          )}
          <Block letter="G" title="Data provenance">
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
              <dt className="text-muted-foreground">Data class</dt><dd>{prov.dataClass ? CLASS_TEXT[prov.dataClass] : "not yet loaded"}</dd>
              <dt className="text-muted-foreground">Source</dt><dd>{prov.source ?? e?.dataRequirements ?? "–"}</dd>
              <dt className="text-muted-foreground">Universe</dt><dd>{prov.universe ?? "–"}</dd>
              <dt className="text-muted-foreground">Period</dt><dd>{prov.window ? prov.window.join(" → ") : "–"}</dd>
              <dt className="text-muted-foreground">As of / last obs.</dt><dd>{prov.asOf ?? "–"}</dd>
              <dt className="text-muted-foreground">Generator</dt><dd>{prov.generator ?? "–"}{prov.nPaths ? " · " + prov.nPaths + " paths" : ""}</dd>
              <dt className="text-muted-foreground">Horizon</dt><dd>{prov.horizon ?? "–"}</dd>
              <dt className="text-muted-foreground">Benchmark</dt><dd>{prov.benchmark ?? "–"}</dd>
              <dt className="text-muted-foreground">Catalog hash</dt><dd className="font-mono">{prov.catalogHash ? String(prov.catalogHash).slice(0, 16) : "–"}</dd>
              <dt className="text-muted-foreground">Run</dt><dd className="font-mono">{prov.runId ? <Link className="underline" href={"/runs?section=registry&id=" + prov.runId}>{shortId(prov.runId)}</Link> : "no run (not computed or not run-based)"}</dd>
              {prov.finishedAt ? <><dt className="text-muted-foreground">Computed</dt><dd>{prov.finishedAt}</dd></> : null}
              {sel.map(([k, v]) => <Fragment key={k}><dt className="text-muted-foreground">Selected {k}</dt><dd>{String(v)}</dd></Fragment>)}
            </dl>
            {e ? <p className="mt-1 text-xs text-muted-foreground">Requires: {e.dataRequirements}</p> : null}
            {note ? <div className="mt-2 rounded border border-border p-2 text-xs">{note}</div> : null}
          </Block>
          {e ? (
            <Block letter="H" title="Related research">
              <ul className="space-y-0.5 text-xs">
                {e.methodologyLinks.map((m) => <li key={m.href}>Learn more: <Link className="underline" href={m.href}>{m.label}</Link></li>)}
                {e.relatedHypotheses.length ? <li>Hypotheses: {e.relatedHypotheses.map((h) => <Link key={h} className="mr-2 underline" href={"/research?section=hypotheses#" + h}>{h}</Link>)}</li> : null}
                {e.related.length ? <li>Related charts: {e.related.filter((r) => VIZ_BY_ID[r]).map((r) => <Link key={r} className="mr-2 underline" href={vizHref(r)}>{r} {VIZ_BY_ID[r].title}</Link>)}</li> : null}
                <li><Link className="underline" href={"/methodology?section=visualizations#ref-" + id}>This chart in the Visualization Reference</Link></li>
              </ul>
            </Block>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
