/**
 * Central visualization-information registry. Every <VisualizationFrame id="…"> must have an entry here;
 * tests/unit/visualization-registry.test.ts fails the build when a rendered ID is missing or incomplete.
 */
import type { VizEntry } from "./viz/define";
import { MARKETS } from "./viz/markets";
import { MULTIASSET } from "./viz/multiasset";
import { REPLAY } from "./viz/replay";
import { PLANNING } from "./viz/planning";
import { PORTFOLIO } from "./viz/portfolio";
import { VALIDATION } from "./viz/validation";
import { PAGE_BY_KEY } from "./routes";

export type { VizEntry } from "./viz/define";
export { REQUIRED_FIELDS } from "./viz/define";

export const VISUALIZATIONS: VizEntry[] = [...PLANNING, ...REPLAY, ...PORTFOLIO, ...MULTIASSET, ...MARKETS, ...VALIDATION];

export const VIZ_BY_ID: Record<string, VizEntry> = Object.fromEntries(VISUALIZATIONS.map((e) => [e.id, e]));

export function vizEntry(id: string): VizEntry | undefined {
  return VIZ_BY_ID[id];
}

/** Deep link to a visualization: page + section + anchor. */
export function vizHref(id: string): string {
  const e = VIZ_BY_ID[id];
  if (!e) return "/methodology?section=visualizations";
  const p = PAGE_BY_KEY[e.page];
  const hasSection = p.sections.some((s) => s.id === e.section);
  return p.path + (hasSection ? "?section=" + e.section : "") + "#" + id;
}
