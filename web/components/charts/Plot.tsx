"use client";
import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import type { Config, Data, Layout } from "plotly.js";

// Plotly is client-only and heavy: load the minified dist through the react-plotly factory
let plotlyLib: typeof import("plotly.js") | null = null;
const PlotlyComponent = dynamic(
  async () => {
    const Plotly = (await import("plotly.js-dist-min")).default;
    plotlyLib = Plotly;
    const createPlotlyComponent = (await import("react-plotly.js/factory")).default;
    return createPlotlyComponent(Plotly);
  },
  { ssr: false, loading: () => <div className="h-full w-full animate-pulse rounded-lg bg-muted/40" /> },
);

export interface VizTokens {
  surface: string;
  text: string;
  text2: string;
  grid: string;
  series: string[];
  divNeg: string;
  divMid: string;
  divPos: string;
}

function readTokens(): VizTokens {
  const css = getComputedStyle(document.documentElement);
  const v = (n: string) => css.getPropertyValue(n).trim();
  return {
    surface: v("--viz-surface"),
    text: v("--viz-text"),
    text2: v("--viz-text-2"),
    grid: v("--viz-grid"),
    series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => v("--viz-s" + i)),
    divNeg: v("--viz-div-neg"),
    divMid: v("--viz-div-mid"),
    divPos: v("--viz-div-pos"),
  };
}

const FALLBACK: VizTokens = {
  surface: "#1a1a19",
  text: "#f0efec",
  text2: "#c3c2b7",
  grid: "rgba(240,239,236,0.08)",
  series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  divNeg: "#e66767",
  divMid: "#383835",
  divPos: "#3987e5",
};

export function useVizTokens(): VizTokens {
  const { resolvedTheme } = useTheme();
  const [tokens, setTokens] = useState<VizTokens>(FALLBACK);
  useEffect(() => {
    // re-read after the theme class lands on <html>
    const id = requestAnimationFrame(() => setTokens(readTokens()));
    return () => cancelAnimationFrame(id);
  }, [resolvedTheme]);
  return tokens;
}

/** react-plotly can keep Plotly's empty-plot default ranges after an update; re-run autorange where no range is set. */
function refreshAutorange(gd: HTMLElement, layout: Partial<Layout>) {
  if (!plotlyLib) return;
  const upd: Record<string, boolean> = {};
  const full = (gd as unknown as { _fullLayout?: Record<string, { range?: unknown[]; type?: string }> })._fullLayout;
  for (const ax of ["xaxis", "yaxis"] as const) {
    if (layout[ax]?.range) continue;
    const r = full?.[ax]?.range;
    const stale = !r || (r[0] === -1 && r[1] === 6) || (r[0] === "2000-01-01" && r[1] === "2001-01-01") || (r[0] === 0 && r[1] === 4);
    if (stale) upd[ax + ".autorange"] = true;
  }
  if (Object.keys(upd).length > 0) void plotlyLib.relayout(gd, upd);
}

export function Plot({
  data,
  layout,
  height = 320,
  config,
  onClick,
}: {
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
  config?: Partial<Config>;
  onClick?: (e: Readonly<Plotly.PlotMouseEvent>) => void;
}) {
  const t = useVizTokens();
  const axis = {
    gridcolor: t.grid,
    zerolinecolor: t.grid,
    linecolor: t.grid,
    tickfont: { color: t.text2, size: 11 },
    title: { font: { color: t.text2, size: 12 } },
  };
  const base: Partial<Layout> = {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: "var(--font-sans), ui-sans-serif, system-ui", color: t.text, size: 12 },
    margin: { l: 56, r: 16, t: 24, b: 44 },
    hovermode: "x unified",
    hoverlabel: { bgcolor: t.surface, bordercolor: t.grid, font: { color: t.text } },
    legend: { orientation: "h", y: 1.12, x: 0, font: { color: t.text2, size: 11 } },
    colorway: t.series,
    autosize: true,
  };
  const merged: Partial<Layout> = {
    ...base,
    ...layout,
    // explicit autorange unless a range is given: Plotly otherwise keeps a stale default date range on re-render
    xaxis: { ...axis, autorange: layout?.xaxis?.range ? false : true, ...(layout?.xaxis ?? {}),
      title: { ...axis.title, ...((layout?.xaxis?.title as object) ?? {}) } },
    yaxis: { ...axis, autorange: layout?.yaxis?.range ? false : true, ...(layout?.yaxis ?? {}),
      title: { ...axis.title, ...((layout?.yaxis?.title as object) ?? {}) } },
  };
  return (
    <div style={{ height }} className="w-full">
      <PlotlyComponent
        // remount when theme tokens resolve: react-plotly's update path can keep a stale default date range
        key={t.surface + t.text}
        data={data}
        layout={merged}
        config={{ displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d"], ...config }}
        style={{ width: "100%", height: "100%" }}
        useResizeHandler
        onClick={onClick}
        onInitialized={(_, gd) => refreshAutorange(gd as unknown as HTMLElement, merged)}
        onUpdate={(_, gd) => refreshAutorange(gd as unknown as HTMLElement, merged)}
      />
    </div>
  );
}
