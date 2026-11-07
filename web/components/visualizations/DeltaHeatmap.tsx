"use client";
import type { Data } from "plotly.js";
import { Plot, useVizTokens } from "./Plot";

/** Diverging Delta-CE heatmap centred at zero; cells with |delta| < 2 SE are hatched. */
export function DeltaHeatmap({
  x,
  y,
  z,
  se,
  shortfall,
  xLabel,
  yLabel,
  xFormat = (v: number) => (v * 100).toFixed(1) + "%",
  onCellClick,
  showSE = true,
  height = 460,
  selected,
}: {
  x: number[];
  y: number[];
  z: number[][];
  se: number[][];
  shortfall?: number[][];
  xLabel: string;
  yLabel: string;
  xFormat?: (v: number) => string;
  onCellClick?: (i: number, j: number) => void;
  showSE?: boolean;
  height?: number;
  selected?: [number, number] | null;
}) {
  const t = useVizTokens();
  const zPct = z.map((row) => row.map((v) => (v === null ? NaN : v * 100)));
  let lim = 0.5;
  for (const row of zPct) for (const v of row) if (Number.isFinite(v)) lim = Math.max(lim, Math.abs(v));
  const xs = x.map(xFormat);
  const ys = y.map((v) => String(v));
  const custom = z.map((row, i) =>
    row.map((v, j) => [
      ((se[i][j] ?? 0) * 100).toFixed(2),
      shortfall ? ((shortfall[i][j] ?? 0) * 100).toFixed(1) : "–",
      Math.abs(v) < 2 * (se[i][j] ?? 0) ? "within 2 SE (not significant)" : "significant",
    ]),
  );
  const data: Data[] = [
    {
      type: "heatmap",
      x: xs,
      y: ys,
      z: zPct,
      zmin: -lim,
      zmax: lim,
      zmid: 0,
      colorscale: [
        [0, t.divNeg],
        [0.5, t.divMid],
        [1, t.divPos],
      ],
      xgap: 2,
      ygap: 2,
      customdata: custom as unknown as Plotly.Datum[][],
      hovertemplate:
        xLabel + " %{x}<br>" + yLabel + " %{y}<br><b>ΔCE %{z:+.2f}%</b> ± %{customdata[0]}%<br>" +
        "P(depletion) %{customdata[1]}%<br>%{customdata[2]}<extra></extra>",
      colorbar: { title: { text: "ΔCE %", side: "right" }, thickness: 10, outlinewidth: 0,
        tickfont: { color: t.text2 } },
      text: zPct.map((row) => row.map((v) => (Number.isFinite(v) ? (v > 0 ? "+" : "") + v.toFixed(1) : ""))) as unknown as string[],
      texttemplate: "%{text}",
      textfont: { size: 10, color: t.text },
    } as Data,
  ];
  if (showSE) {
    const hx: string[] = [];
    const hy: string[] = [];
    z.forEach((row, i) =>
      row.forEach((v, j) => {
        if (Math.abs(v) < 2 * (se[i][j] ?? 0)) {
          hx.push(xs[j]);
          hy.push(ys[i]);
        }
      }),
    );
    data.push({ type: "scatter", mode: "markers", x: hx, y: hy, hoverinfo: "skip", showlegend: false,
      marker: { symbol: "line-ne-open", size: 22, color: t.text2, line: { width: 1, color: t.text2 }, opacity: 0.55 } });
  }
  const shapes = selected
    ? [{ type: "rect" as const, xref: "x" as const, yref: "y" as const,
        x0: selected[1] - 0.5, x1: selected[1] + 0.5, y0: selected[0] - 0.5, y1: selected[0] + 0.5,
        line: { color: t.text, width: 2 } }]
    : [];
  return (
    <Plot
      data={data}
      height={height}
      layout={{
        hovermode: "closest",
        xaxis: { title: { text: xLabel }, type: "category", showgrid: false },
        yaxis: { title: { text: yLabel }, type: "category", showgrid: false },
        margin: { l: 64, r: 16, t: 16, b: 52 },
        shapes,
      }}
      onClick={(e) => {
        const p = e.points?.[0];
        if (!p || !onCellClick) return;
        const j = xs.indexOf(String(p.x));
        const i = ys.indexOf(String(p.y));
        if (i >= 0 && j >= 0) onCellClick(i, j);
      }}
    />
  );
}
