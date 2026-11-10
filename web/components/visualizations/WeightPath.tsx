"use client";
import type { Data } from "plotly.js";
import { Plot, useVizTokens } from "./Plot";
import { assetLabel } from "@/lib/format";

/** Stacked area of mean portfolio weights by age (series colour follows the asset, never its rank). */
export function WeightPath({
  ages,
  assets,
  weights,
  height = 300,
  allAssets,
}: {
  ages: number[];
  assets: string[];
  weights: number[][];
  height?: number;
  allAssets?: string[];
}) {
  const t = useVizTokens();
  const order = allAssets ?? assets;
  const data: Data[] = [];
  assets.forEach((a, k) => {
    const y = weights.map((w) => w[k]);
    if (Math.max(...y) < 1e-4) return;
    const color = t.series[order.indexOf(a) % t.series.length];
    data.push({
      x: ages.slice(0, weights.length),
      y,
      type: "scatter",
      mode: "lines",
      stackgroup: "w",
      name: assetLabel(a),
      line: { width: 0.5, color },
      fillcolor: color,
      hovertemplate: assetLabel(a) + " %{y:.0%}<extra></extra>",
    });
  });
  return (
    <Plot
      data={data}
      height={height}
      layout={{ xaxis: { title: { text: "Age" } }, yaxis: { title: { text: "Weight" }, tickformat: ".0%", range: [0, 1] } }}
    />
  );
}
