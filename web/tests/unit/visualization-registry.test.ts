/**
 * Coverage of the visualization-information registry. Fails the build when:
 *  - a rendered <Viz id> / <VisualizationFrame id> has no registry entry (no exemptions),
 *  - a registry entry is incomplete or never rendered,
 *  - an entry points at a page/section that does not exist, or a cross-reference is dangling.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { REQUIRED_FIELDS, VISUALIZATIONS, VIZ_BY_ID, vizHref } from "@/lib/research/visualization-registry";
import { JOURNEYS, PAGES, PAGE_BY_KEY, QUESTIONS, WORKFLOW } from "@/lib/research/routes";

const ROOT = path.resolve(__dirname, "../..");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => {
    const p = path.join(dir, f);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.(tsx|ts)$/.test(f) ? [p] : [];
  });
}

const files = [...sources(path.join(ROOT, "components")), ...sources(path.join(ROOT, "app"))];
const rendered = new Map<string, string[]>();
for (const f of files) {
  const s = readFileSync(f, "utf8");
  for (const m of s.matchAll(/<(?:Viz|VisualizationFrame)\s+id="([A-Za-z]{2}-[0-9a-z]+)"/g)) {
    rendered.set(m[1], [...(rendered.get(m[1]) ?? []), path.relative(ROOT, f)]);
  }
  for (const m of s.matchAll(/<PendingFrames\s+ids=\{\[([^\]]+)\]\}/g)) {
    for (const id of m[1].match(/"([A-Za-z]{2}-[0-9a-z]+)"/g) ?? []) rendered.set(id.slice(1, -1), [...(rendered.get(id.slice(1, -1)) ?? []), path.relative(ROOT, f)]);
  }
  // dynamic ids are not allowed (they would escape this check), except inside the PendingFrames helper itself
  if (!f.endsWith("VisualizationFrame.tsx")) expect(s.match(/<(?:Viz|VisualizationFrame)\s+id=\{/g), f).toBeNull();
}

describe("visualization registry", () => {
  it("has unique IDs", () => {
    const ids = VISUALIZATIONS.map((v) => v.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("covers every rendered visualization", () => {
    const missing = [...rendered.keys()].filter((id) => !VIZ_BY_ID[id]);
    expect(missing, "rendered without a registry entry").toEqual([]);
  });

  it("has no orphan entries (every entry is rendered somewhere)", () => {
    const orphans = VISUALIZATIONS.map((v) => v.id).filter((id) => !rendered.has(id));
    expect(orphans, "registry entries never rendered").toEqual([]);
  });

  it.each(VISUALIZATIONS.map((v) => [v.id, v] as const))("%s has every required field", (_id, v) => {
    for (const f of REQUIRED_FIELDS) {
      const val = (v as unknown as Record<string, unknown>)[f];
      expect(val, `${v.id}.${f}`).toBeDefined();
      if (typeof val === "string") expect(val.trim().length, `${v.id}.${f}`).toBeGreaterThan(f === "units" ? 0 : 3);
      if (f === "assumptions" || f === "limitations" || f === "methodologyLinks") expect((val as unknown[]).length, `${v.id}.${f}`).toBeGreaterThan(0);
    }
    const axes = v.axes;
    expect(Boolean(axes.x || axes.y || axes.color || axes.other), `${v.id} axes`).toBe(true);
  });

  it("points every entry at a real page and section", () => {
    for (const v of VISUALIZATIONS) {
      const p = PAGE_BY_KEY[v.page];
      expect(p, v.id).toBeDefined();
      if (p.sections.length) expect(p.sections.map((s) => s.id), v.id).toContain(v.section);
      expect(vizHref(v.id).startsWith(p.path)).toBe(true);
    }
  });

  it("has no dangling cross-references", () => {
    for (const v of VISUALIZATIONS) for (const r of v.related) expect(VIZ_BY_ID[r], `${v.id} → ${r}`).toBeDefined();
    for (const q of QUESTIONS) for (const c of q.charts) expect(VIZ_BY_ID[c], `${q.id} → ${c}`).toBeDefined();
    for (const v of VISUALIZATIONS) for (const m of v.methodologyLinks) expect(m.href.startsWith("/methodology")).toBe(true);
  });
});

describe("route registry", () => {
  it("defines exactly the 13 unified routes in four groups", () => {
    expect(PAGES.map((p) => p.path)).toEqual(["/", "/withdrawal-lab", "/lifecycle-flows", "/permanent-portfolio", "/rebalance", "/optimize",
      "/fixed-income", "/market-state", "/scenarios", "/compare", "/research", "/runs", "/methodology"]);
    expect(new Set(PAGES.map((p) => p.group)).size).toBe(4);
  });

  it("has an app route for every page and no retired routes", () => {
    for (const p of PAGES) {
      const f = path.join(ROOT, "app", p.path === "/" ? "" : p.path.slice(1), "page.tsx");
      expect(() => statSync(f), f).not.toThrow();
    }
    for (const old of ["lab", "simulate"]) expect(() => statSync(path.join(ROOT, "app", old))).toThrow();
  });

  it("uses no generation labels in page names, sections or nav", () => {
    const text = JSON.stringify(PAGES);
    expect(text).not.toMatch(/\(v1\)|\(v2\)|\blegacy\b|Legacy|A · Overview/);
  });

  it("references only existing pages and sections in questions, workflow and journeys", () => {
    const sec = (k: keyof typeof PAGE_BY_KEY, s?: string) => !s || PAGE_BY_KEY[k].sections.some((x) => x.id === s);
    for (const q of QUESTIONS) for (const st of [q.start, ...q.next]) expect(sec(st.page, st.section), q.id).toBe(true);
    for (const j of JOURNEYS) for (const st of j.steps) expect(sec(st.page, st.section), j.title).toBe(true);
    for (const w of WORKFLOW) for (const k of w.pages) expect(PAGE_BY_KEY[k]).toBeDefined();
    for (const p of PAGES) for (const r of p.related) expect(PAGE_BY_KEY[r]).toBeDefined();
  });

  it("gives every page section at least one visualization (or a documented reference view)", () => {
    for (const p of PAGES) for (const s of p.sections) {
      if (p.key === "methodology" && s.id === "visualizations") continue; // reference listing generated from the registry
      expect(VISUALIZATIONS.some((v) => v.page === p.key && v.section === s.id), p.key + "/" + s.id).toBe(true);
    }
  });
});
