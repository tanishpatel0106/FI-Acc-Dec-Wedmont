"use client";
import type { Data } from "plotly.js";
import { Plot, useVizTokens } from "./Plot";
import type { Quantiles } from "@/lib/api/types";

function alpha(hex: string, a: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

export function FanChart({
  ages,
  q,
  benchmark,
  title,
  yTitle,
  retireAge,
  height = 320,
  money = true,
}: {
  ages: number[];
  q: Quantiles;
  benchmark?: Quantiles;
  title?: string;
  yTitle?: string;
  retireAge?: number;
  height?: number;
  money?: boolean;
}) {
  const t = useVizTokens();
  const x = ages.slice(0, q.p50.length);
  const c = t.series[0];
  const fmt = money ? "$,.0f" : ".2f";
  const data: Data[] = [
    { x, y: q.p95, type: "scatter", mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
    { x, y: q.p05, type: "scatter", mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: alpha(c, 0.14),
      name: "5–95%", hovertemplate: "p05 %{y:" + fmt + "}<extra></extra>" },
    { x, y: q.p75, type: "scatter", mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
    { x, y: q.p25, type: "scatter", mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: alpha(c, 0.3),
      name: "25–75%", hovertemplate: "p25 %{y:" + fmt + "}<extra></extra>" },
    { x, y: q.p50, type: "scatter", mode: "lines", line: { width: 2, color: c }, name: "Median (policy)",
      hovertemplate: "median %{y:" + fmt + "}<extra></extra>" },
  ];
  if (benchmark) {
    data.push({ x, y: benchmark.p50.slice(0, x.length), type: "scatter", mode: "lines",
      line: { width: 2, color: t.series[1], dash: "dash" }, name: "Median (benchmark)",
      hovertemplate: "benchmark %{y:" + fmt + "}<extra></extra>" });
  }
  const shapes = retireAge
    ? [{ type: "line" as const, x0: retireAge, x1: retireAge, yref: "paper" as const, y0: 0, y1: 1,
        line: { color: t.text2, width: 1, dash: "dot" as const } }]
    : [];
  return (
    <Plot
      data={data}
      height={height}
      layout={{
        title: title ? { text: title, font: { size: 13 }, x: 0, xanchor: "left" } : undefined,
        xaxis: { title: { text: "Age" } },
        yaxis: { title: { text: yTitle ?? "" }, tickformat: money ? "$~s" : undefined, rangemode: "tozero" },
        shapes,
      }}
    />
  );
}
