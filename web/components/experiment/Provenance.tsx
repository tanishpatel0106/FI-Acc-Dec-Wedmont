"use client";
import { shortId } from "@/lib/format";
import { reportUrl } from "@/lib/api/client";

export function Provenance({ meta, runId }: { meta?: Record<string, unknown> | null; runId?: string | null }) {
  if (!meta && !runId) return null;
  const m = (meta ?? {}) as Record<string, string>;
  const id = runId ?? m.run_id;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-muted-foreground">
      <span>run {shortId(id)}</span>
      {m.spec_hash ? <span>spec {shortId(m.spec_hash)}</span> : null}
      {m.catalog_hash ? <span>catalog {String(m.catalog_hash).slice(0, 8)}</span> : null}
      {m.engine_version ? <span>engine {m.engine_version}</span> : null}
      {id ? (
        <span className="space-x-2 font-sans">
          <a className="underline" href={reportUrl(id, "pdf")}>PDF</a>
          <a className="underline" href={reportUrl(id, "csv")}>CSV</a>
          <a className="underline" href={reportUrl(id, "bibtex")}>BibTeX</a>
        </span>
      ) : null}
    </div>
  );
}
