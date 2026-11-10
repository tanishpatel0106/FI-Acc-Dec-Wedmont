"use client";
import { useQuery } from "@tanstack/react-query";
import { tableFromIPC } from "apache-arrow";
import type { Data } from "plotly.js";
import { fetchArrow } from "@/lib/api/client";
import { Plot, useVizTokens } from "./Plot";

/** Individual wealth paths, transported as Arrow IPC (application/vnd.apache.arrow.stream) and decoded in the browser. */
export function SamplePaths({ runId, n = 60, height = 300 }: { runId: string; n?: number; height?: number }) {
  const t = useVizTokens();
  const q = useQuery({
    queryKey: ["paths", runId, n],
    queryFn: async () => {
      const buf = await fetchArrow("/v1/experiments/" + runId + "/paths?n=" + n);
      const table = tableFromIPC(new Uint8Array(buf));
      const path = table.getChild("path")!.toArray() as Int32Array | BigInt64Array;
      const age = table.getChild("age")!.toArray() as Float64Array;
      const wealth = table.getChild("wealth")!.toArray() as Float64Array;
      const out = new Map<number, { x: number[]; y: number[] }>();
      for (let i = 0; i < table.numRows; i++) {
        const p = Number(path[i]);
        if (!out.has(p)) out.set(p, { x: [], y: [] });
        out.get(p)!.x.push(age[i]);
        out.get(p)!.y.push(wealth[i]);
      }
      return { paths: [...out.values()], bytes: buf.byteLength };
    },
    staleTime: Infinity,
  });
  if (q.isLoading) return <div className="animate-pulse rounded-lg bg-muted/40" style={{ height }} />;
  if (q.error || !q.data) return <div className="text-xs text-muted-foreground">Sample paths unavailable for this run.</div>;
  const data: Data[] = q.data.paths.map((p, i) => ({
    x: p.x, y: p.y, type: "scatter", mode: "lines", showlegend: false, hoverinfo: "skip",
    line: { width: 1, color: i === 0 ? t.series[1] : t.series[0] }, opacity: i === 0 ? 1 : 0.25,
  }));
  return (
    <>
      <Plot height={height} data={data} layout={{ hovermode: false, yaxis: { tickformat: "$~s", title: { text: "real wealth" } }, xaxis: { title: { text: "Age" } } }} />
      <div className="text-[11px] text-muted-foreground">{q.data.paths.length} paths · {(q.data.bytes / 1024).toFixed(0)} KB Arrow IPC · first path highlighted</div>
    </>
  );
}
