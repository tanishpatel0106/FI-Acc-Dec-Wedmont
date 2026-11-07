"use client";
import type { Data, Layout } from "plotly.js";
import { Plot, useVizTokens } from "@/components/visualizations/Plot";

/* eslint-disable @typescript-eslint/no-explicit-any */
// Stable asset colours (identity follows the entity, never its rank): token index per asset
const ASSET_SLOT: Record<string, number> = {
  us_eq: 0, intl_eq: 1, em_eq: 4, reit: 1, ust_10y: 2, ust_2y: 2, ust_5y: 2, ust_20y: 5, ust_30y: 5, tips: 4,
  ig_credit: 6, hy_credit: 7, gold: 3, tbill: -1,
};

export function useAssetColor() {
  const t = useVizTokens();
  return (a: string, i = 0) => {
    const s = ASSET_SLOT[a];
    if (s === -1) return t.text2;
    return t.series[(s ?? i) % t.series.length];
  };
}

export function useSeries() {
  return useVizTokens().series;
}

const pctFmt = ".0%";

/** Heatmap with optional mask (hatched / greyed cells), diverging or sequential scale, click-through. */
export function Heat({ x, y, z, xTitle, yTitle, zTitle, diverging = false, mask, onClick, height = 360, zfmt = ".0%",
  xfmt, yfmt, text = true, zmin, zmax, contours, custom, hover }: {
  x: (number | string)[]; y: (number | string)[]; z: (number | null)[][]; xTitle: string; yTitle: string; zTitle: string;
  diverging?: boolean; mask?: (boolean | number)[][]; onClick?: (i: number, j: number) => void; height?: number;
  zfmt?: string; xfmt?: (v: any) => string; yfmt?: (v: any) => string; text?: boolean; zmin?: number; zmax?: number;
  contours?: { level: number; label: string }[]; custom?: any[][]; hover?: string;
}) {
  const t = useVizTokens();
  const xs = x.map((v) => (xfmt ? xfmt(v) : String(v)));
  const ys = y.map((v) => (yfmt ? yfmt(v) : String(v)));
  let lim = 0;
  for (const r of z) for (const v of r) if (v !== null && Number.isFinite(v)) lim = Math.max(lim, Math.abs(v));
  const zm = z.map((r, i) => r.map((v, j) => (mask && mask[i]?.[j] ? null : v)));
  const data: Data[] = [{
    type: "heatmap", x: xs, y: ys, z: zm as any,
    zmin: diverging ? -lim || -1 : zmin, zmax: diverging ? lim || 1 : zmax, zmid: diverging ? 0 : undefined,
    colorscale: diverging ? [[0, t.divNeg], [0.5, t.divMid], [1, t.divPos]] : [[0, t.divMid], [1, t.series[0]]],
    xgap: 1, ygap: 1, customdata: custom as any,
    hovertemplate: hover ?? (xTitle + " %{x}<br>" + yTitle + " %{y}<br>" + zTitle + " %{z:" + zfmt + "}<extra></extra>"),
    colorbar: { title: { text: zTitle, side: "right" }, thickness: 10, outlinewidth: 0, tickformat: zfmt },
    texttemplate: text && xs.length * ys.length <= 160 ? "%{z:" + zfmt + "}" : undefined, textfont: { size: 9 },
  } as Data];
  if (mask) {
    const hx: string[] = [], hy: string[] = [];
    mask.forEach((r, i) => r.forEach((m, j) => { if (m) { hx.push(xs[j]); hy.push(ys[i]); } }));
    if (hx.length) data.push({ type: "scatter", mode: "markers", x: hx, y: hy, hoverinfo: "skip", showlegend: false,
      marker: { symbol: "x-thin-open", size: 9, color: t.text2, line: { width: 1, color: t.text2 } } } as Data);
  }
  if (contours) {
    for (const c of contours) {
      data.push({ type: "contour", x: xs, y: ys, z: z as any, showscale: false, hoverinfo: "skip",
        contours: { start: c.level, end: c.level, size: 1, coloring: "lines", showlabels: true,
          labelfont: { size: 9, color: t.text } }, line: { width: 2, color: t.text }, name: c.label } as Data);
    }
  }
  return (
    <Plot height={height} data={data} onClick={(e) => {
      const p = e.points?.[0];
      if (!p || !onClick) return;
      const j = xs.indexOf(String(p.x)); const i = ys.indexOf(String(p.y));
      if (i >= 0 && j >= 0) onClick(i, j);
    }} layout={{ hovermode: "closest", xaxis: { title: { text: xTitle }, type: "category", showgrid: false },
      yaxis: { title: { text: yTitle }, type: "category", showgrid: false }, margin: { l: 64, r: 16, t: 16, b: 52 } }} />
  );
}

export interface Line { name: string; x: (number | string)[]; y: (number | null)[]; lo?: (number | null)[]; hi?: (number | null)[];
  color?: string; dash?: string; mode?: "lines" | "markers" | "lines+markers"; width?: number }

/** Lines with optional uncertainty ribbons. One y-axis only. */
export function Lines({ lines, xTitle, yTitle, yfmt = "", xfmt, height = 300, shapes, annotations, xType, yRange, legend = true }: {
  lines: Line[]; xTitle: string; yTitle: string; yfmt?: string; xfmt?: string; height?: number; shapes?: any[]; annotations?: any[];
  xType?: "date" | "linear" | "category"; yRange?: [number, number]; legend?: boolean;
}) {
  const s = useSeries();
  const data: Data[] = [];
  lines.forEach((l, i) => {
    const c = l.color ?? s[i % s.length];
    if (l.lo && l.hi) {
      data.push({ type: "scatter", x: [...l.x, ...[...l.x].reverse()], y: [...l.hi, ...[...l.lo].reverse()] as any, fill: "toself",
        fillcolor: c + "26", line: { width: 0 }, hoverinfo: "skip", showlegend: false, name: l.name + " CI" } as Data);
    }
    data.push({ type: "scatter", mode: l.mode ?? "lines", x: l.x, y: l.y as any, name: l.name,
      line: { color: c, width: l.width ?? 2, dash: l.dash as any }, marker: { size: 8, color: c } } as Data);
  });
  return <Plot height={height} data={data} layout={{ showlegend: legend && lines.length > 1, shapes, annotations,
    xaxis: { title: { text: xTitle }, tickformat: xfmt, type: xType }, yaxis: { title: { text: yTitle }, tickformat: yfmt, range: yRange } }} />;
}

export interface ForestRow { label: string; est: number | null; lo?: number | null; hi?: number | null; note?: string; group?: string }

/** Forest plot: point estimate with CI bars and a reference line (zero effect by default). */
export function Forest({ rows, xTitle, xfmt = "", ref = 0, height, refLabel }: { rows: ForestRow[]; xTitle: string; xfmt?: string;
  ref?: number | null; height?: number; refLabel?: string }) {
  const t = useVizTokens();
  const ok = rows.filter((r) => r.est !== null && r.est !== undefined);
  const missing = rows.filter((r) => r.est === null || r.est === undefined);
  const labels = rows.map((r) => r.label);
  const data: Data[] = [{
    type: "scatter", mode: "markers", y: ok.map((r) => r.label), x: ok.map((r) => r.est as number), name: "estimate",
    marker: { size: 9, color: t.series[0], symbol: "diamond" },
    error_x: { type: "data", symmetric: false, array: ok.map((r) => (r.hi ?? r.est!) - r.est!),
      arrayminus: ok.map((r) => r.est! - (r.lo ?? r.est!)), color: t.series[0], thickness: 1.5, width: 4 },
    customdata: ok.map((r) => [r.lo ?? "–", r.hi ?? "–", r.note ?? ""]) as any,
    hovertemplate: "%{y}<br>%{x:" + xfmt + "} [%{customdata[0]:" + xfmt + "}, %{customdata[1]:" + xfmt + "}]<br>%{customdata[2]}<extra></extra>",
  } as Data];
  if (missing.length) data.push({ type: "scatter", mode: "text", y: missing.map((r) => r.label), x: missing.map(() => ref ?? 0),
    text: missing.map((r) => r.note ?? "not identified"), textfont: { color: t.text2, size: 10 }, textposition: "middle right",
    hoverinfo: "skip", showlegend: false } as Data);
  const shapes = ref === null ? [] : [{ type: "line", x0: ref, x1: ref, yref: "paper", y0: 0, y1: 1, line: { color: t.text2, dash: "dot", width: 1 } }];
  return <Plot height={height ?? Math.max(160, 36 + 26 * rows.length)} data={data}
    layout={{ hovermode: "closest", showlegend: false, shapes: shapes as any, margin: { l: 190, r: 24, t: 12, b: 44 },
      annotations: refLabel ? [{ x: ref ?? 0, y: 1.02, yref: "paper", text: refLabel, showarrow: false, font: { size: 10, color: t.text2 } }] : [],
      xaxis: { title: { text: xTitle }, tickformat: xfmt }, yaxis: { type: "category", categoryarray: [...labels].reverse(), categoryorder: "array", automargin: true } }} />;
}

/** Percentile fan (p05-p95, p25-p75, median). */
export function Fan({ x, q, name, color, xTitle, yTitle, yfmt = "$,.0f", height = 300, compare, vline }: {
  x: (number | string)[]; q: Record<string, number[]>; name: string; color?: string; xTitle: string; yTitle: string; yfmt?: string;
  height?: number; compare?: { q: Record<string, number[]>; name: string; color?: string }; vline?: { x: number | string; label: string };
}) {
  const s = useSeries();
  const t = useVizTokens();
  const band = (qq: Record<string, number[]>, c: string, nm: string, xx: (number | string)[]): Data[] => {
    const n = Math.min(xx.length, qq.p50?.length ?? 0);
    const X = xx.slice(0, n);
    const sl = (k: string) => (qq[k] ?? []).slice(0, n);
    return [
      { type: "scatter", x: [...X, ...[...X].reverse()], y: [...sl("p95"), ...sl("p05").reverse()], fill: "toself", fillcolor: c + "1f",
        line: { width: 0 }, hoverinfo: "skip", showlegend: false } as Data,
      { type: "scatter", x: [...X, ...[...X].reverse()], y: [...sl("p75"), ...sl("p25").reverse()], fill: "toself", fillcolor: c + "40",
        line: { width: 0 }, hoverinfo: "skip", showlegend: false } as Data,
      { type: "scatter", mode: "lines", x: X, y: sl("p50"), name: nm + " median", line: { color: c, width: 2 } } as Data,
    ];
  };
  const data = [...band(q, color ?? s[0], name, x), ...(compare ? band(compare.q, compare.color ?? s[1], compare.name, x) : [])];
  const shapes = vline ? [{ type: "line", x0: vline.x, x1: vline.x, yref: "paper", y0: 0, y1: 1, line: { color: t.text2, dash: "dash", width: 1 } }] : [];
  const annotations = vline ? [{ x: vline.x, y: 1, yref: "paper", text: vline.label, showarrow: false, font: { size: 10, color: t.text2 }, xanchor: "left" }] : [];
  return <Plot height={height} data={data} layout={{ shapes: shapes as any, annotations: annotations as any,
    xaxis: { title: { text: xTitle } }, yaxis: { title: { text: yTitle }, tickformat: yfmt } }} />;
}

export function Bars({ x, series, xTitle, yTitle, yfmt = "", height = 280, stacked = false, horizontal = false, colors }: {
  x: (string | number)[]; series: { name: string; y: (number | null)[]; color?: string; err?: [number[], number[]] }[]; xTitle: string; yTitle: string;
  yfmt?: string; height?: number; stacked?: boolean; horizontal?: boolean; colors?: string[];
}) {
  const s = useSeries();
  const data: Data[] = series.map((se, i) => ({
    type: "bar", name: se.name, orientation: horizontal ? "h" : "v",
    x: horizontal ? se.y : x, y: horizontal ? x : se.y, marker: { color: colors ? colors : se.color ?? s[i % s.length] },
    error_y: se.err && !horizontal ? { type: "data", symmetric: false, array: se.err[1], arrayminus: se.err[0], thickness: 1.2, width: 3 } : undefined,
    hovertemplate: "%{" + (horizontal ? "y" : "x") + "}: %{" + (horizontal ? "x" : "y") + ":" + yfmt + "}<extra>" + se.name + "</extra>",
  } as Data));
  return <Plot height={height} data={data} layout={{ barmode: stacked ? "stack" : "group", bargap: 0.25, hovermode: "closest",
    showlegend: series.length > 1, margin: horizontal ? { l: 170, r: 16, t: 16, b: 44 } : undefined,
    xaxis: horizontal ? { title: { text: yTitle }, tickformat: yfmt } : { title: { text: xTitle }, type: "category" },
    yaxis: horizontal ? { type: "category", automargin: true } : { title: { text: yTitle }, tickformat: yfmt } }} />;
}

export function Scatter({ pts, xTitle, yTitle, xfmt = "", yfmt = "", height = 320, diagonal = false, shapes, onClick }: {
  pts: { name: string; x: number[]; y: number[]; text?: string[]; color?: string; size?: number | number[]; symbol?: string | string[] }[];
  xTitle: string; yTitle: string; xfmt?: string; yfmt?: string; height?: number; diagonal?: boolean; shapes?: any[];
  onClick?: (seriesIdx: number, pointIdx: number) => void;
}) {
  const s = useSeries();
  const t = useVizTokens();
  const data: Data[] = pts.map((p, i) => ({ type: "scatter", mode: "markers", name: p.name, x: p.x, y: p.y, text: p.text,
    marker: { size: p.size ?? 8, color: p.color ?? s[i % s.length], symbol: p.symbol as any, line: { width: 1, color: t.surface } },
    hovertemplate: (p.text ? "%{text}<br>" : "") + xTitle + " %{x:" + xfmt + "}<br>" + yTitle + " %{y:" + yfmt + "}<extra>" + p.name + "</extra>" } as Data));
  let sh = shapes ?? [];
  if (diagonal) {
    const all = pts.flatMap((p) => [...p.x, ...p.y]).filter(Number.isFinite);
    const lo = Math.min(...all), hi = Math.max(...all);
    sh = [...sh, { type: "line", x0: lo, y0: lo, x1: hi, y1: hi, line: { color: t.text2, dash: "dot", width: 1 } }];
  }
  return <Plot height={height} data={data} onClick={(e) => { const p = e.points?.[0]; if (p && onClick) onClick(p.curveNumber, p.pointIndex); }}
    layout={{ hovermode: "closest", shapes: sh as any, showlegend: pts.length > 1,
      xaxis: { title: { text: xTitle }, tickformat: xfmt }, yaxis: { title: { text: yTitle }, tickformat: yfmt } }} />;
}

/** Waterfall with explicit total; residual shown as its own bar so the decomposition closes visibly. */
export function Waterfall({ labels, values, yTitle, yfmt = "$,.0f", height = 300, totalLabel = "total" }: {
  labels: string[]; values: number[]; yTitle: string; yfmt?: string; height?: number; totalLabel?: string;
}) {
  const t = useVizTokens();
  return <Plot height={height} data={[{ type: "waterfall", x: [...labels, totalLabel], y: [...values, 0],
    measure: [...labels.map(() => "relative"), "total"], connector: { line: { color: t.grid } },
    increasing: { marker: { color: t.divPos } }, decreasing: { marker: { color: t.divNeg } }, totals: { marker: { color: t.text2 } },
    texttemplate: "%{y:" + yfmt + "}", textposition: "outside", hovertemplate: "%{x}: %{y:" + yfmt + "}<extra></extra>" } as Data]}
    layout={{ showlegend: false, hovermode: "closest", xaxis: { type: "category" }, yaxis: { title: { text: yTitle }, tickformat: yfmt } }} />;
}

export function Ternary({ a, b, c, z, labels, zTitle, masked, height = 380, zfmt = "$,.0f" }: {
  a: number[]; b: number[]; c: number[]; z: (number | null)[]; labels: [string, string, string]; zTitle: string; masked?: boolean[];
  height?: number; zfmt?: string;
}) {
  const t = useVizTokens();
  const keep = z.map((v, i) => v !== null && !(masked?.[i]));
  const data: Data[] = [{ type: "scatterternary", mode: "markers", a: a.filter((_, i) => keep[i]), b: b.filter((_, i) => keep[i]),
    c: c.filter((_, i) => keep[i]), marker: { size: 11, color: z.filter((_, i) => keep[i]) as number[], colorscale: [[0, t.divMid], [1, t.series[0]]],
      colorbar: { title: { text: zTitle }, thickness: 10, tickformat: zfmt }, line: { width: 1, color: t.surface } },
    hovertemplate: labels[0] + " %{a:.0%}<br>" + labels[1] + " %{b:.0%}<br>" + labels[2] + " %{c:.0%}<br>" + zTitle + " %{marker.color:" + zfmt + "}<extra></extra>" } as Data];
  if (masked?.some(Boolean)) data.push({ type: "scatterternary", mode: "markers", a: a.filter((_, i) => masked[i]), b: b.filter((_, i) => masked[i]),
    c: c.filter((_, i) => masked[i]), marker: { symbol: "x-thin-open", size: 9, color: t.text2 }, name: "masked (no data)", hoverinfo: "name" } as Data);
  const ax = (title: string) => ({ title: { text: title, font: { size: 11, color: t.text2 } }, tickformat: pctFmt, gridcolor: t.grid,
    linecolor: t.grid, tickfont: { color: t.text2, size: 10 } });
  return <Plot height={height} data={data} layout={{ showlegend: false, hovermode: "closest",
    ternary: { sum: 1, aaxis: ax(labels[0]), baxis: ax(labels[1]), caxis: ax(labels[2]), bgcolor: "rgba(0,0,0,0)" } } as Partial<Layout>} />;
}

export function Violin({ groups, yTitle, yfmt = "$,.0f", height = 300 }: { groups: { name: string; y: number[] }[]; yTitle: string; yfmt?: string; height?: number }) {
  const s = useSeries();
  return <Plot height={height} data={groups.map((g, i) => ({ type: "violin", y: g.y, name: g.name, box: { visible: true },
    meanline: { visible: true }, line: { color: s[i % s.length] }, points: false } as Data))}
    layout={{ showlegend: false, hovermode: "closest", yaxis: { title: { text: yTitle }, tickformat: yfmt } }} />;
}

export function Histo({ bars, xTitle, yTitle = "count", height = 260, xfmt = "" }: { bars: { name: string; x: (number | string)[]; y: number[] }[];
  xTitle: string; yTitle?: string; height?: number; xfmt?: string }) {
  const s = useSeries();
  return <Plot height={height} data={bars.map((b, i) => ({ type: "bar", x: b.x, y: b.y, name: b.name, opacity: bars.length > 1 ? 0.7 : 1,
    marker: { color: s[i % s.length] } } as Data))} layout={{ barmode: "overlay", bargap: 0.05, showlegend: bars.length > 1,
    xaxis: { title: { text: xTitle }, tickformat: xfmt }, yaxis: { title: { text: yTitle } } }} />;
}

export function Matrix({ labels, z, zfmt = ".2f", height = 300, zTitle = "" }: { labels: string[]; z: number[][]; zfmt?: string; height?: number; zTitle?: string }) {
  const t = useVizTokens();
  return <Plot height={height} data={[{ type: "heatmap", x: labels, y: labels, z, zmin: 0, zmax: 1, colorscale: [[0, t.divMid], [1, t.series[0]]],
    texttemplate: "%{z:" + zfmt + "}", xgap: 2, ygap: 2, colorbar: { title: { text: zTitle }, thickness: 10 },
    hovertemplate: "from %{y} to %{x}: %{z:" + zfmt + "}<extra></extra>" } as Data]}
    layout={{ hovermode: "closest", xaxis: { type: "category", title: { text: "to" } }, yaxis: { type: "category", autorange: "reversed", title: { text: "from" } } }} />;
}

export const pct = (v: number | null | undefined, d = 1) => (v === null || v === undefined || !Number.isFinite(v) ? "–" : (v * 100).toFixed(d) + "%");
export const spct = (v: number | null | undefined, d = 2) => (v === null || v === undefined || !Number.isFinite(v) ? "–" : (v > 0 ? "+" : "") + (v * 100).toFixed(d) + "%");
export const usd = (v: number | null | undefined) => (v === null || v === undefined || !Number.isFinite(v) ? "–" : "$" + Math.round(v).toLocaleString("en-US"));
export const ci = (lo?: number | null, hi?: number | null, f: (v: number) => string = (v) => pct(v)) =>
  lo === null || lo === undefined || hi === null || hi === undefined || !Number.isFinite(lo) || !Number.isFinite(hi) ? "CI not available" : "95% CI " + f(lo) + " to " + f(hi);

/** Raw-sample histogram with an optional marked value (e.g. the actual outcome). */
export function SampleHist({ values, xTitle, xfmt = "", marker, markerLabel, height = 260, nbins = 30 }: { values: number[]; xTitle: string; xfmt?: string;
  marker?: number; markerLabel?: string; height?: number; nbins?: number }) {
  const t = useVizTokens();
  const shapes = marker === undefined ? [] : [{ type: "line", x0: marker, x1: marker, yref: "paper", y0: 0, y1: 1, line: { color: t.series[1], width: 2 } }];
  const annotations = marker === undefined ? [] : [{ x: marker, y: 1, yref: "paper", text: markerLabel ?? "actual", showarrow: false, xanchor: "left", font: { size: 10, color: t.text2 } }];
  return <Plot height={height} data={[{ type: "histogram", x: values, nbinsx: nbins, marker: { color: t.series[0] }, hovertemplate: "%{x}: %{y}<extra></extra>" } as Data]}
    layout={{ showlegend: false, shapes: shapes as any, annotations: annotations as any, bargap: 0.05, xaxis: { title: { text: xTitle }, tickformat: xfmt }, yaxis: { title: { text: "count" } } }} />;
}
