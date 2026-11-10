import { expect, test, type Page } from "@playwright/test";
import { PAGES, QUESTIONS } from "../../lib/research/routes";
import { VISUALIZATIONS, vizHref } from "../../lib/research/visualization-registry";

/**
 * Unified application end-to-end tests. Run against `make api` (with persisted study runs) and a built web
 * app. Expensive computation must never start on page load: every POST is recorded and checked.
 */
const FORBIDDEN = /\(v1\)|\(v2\)|\bLegacy\b|legacy overview|A · Overview|Research command center \(v2\)/;

function watch(page: Page) {
  const errors: string[] = [];
  const launches: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error" && /hydrat|did not match/i.test(m.text())) errors.push(m.text()); });
  page.on("request", (r) => {
    const u = r.url();
    if (r.method() === "POST" && /\/v1\/(studies|experiments|sweeps|compare|research|reports)/.test(u) && !/submit=false/.test(u)) launches.push(u);
  });
  return { errors, launches };
}

async function settle(page: Page) {
  await page.waitForLoadState("networkidle", { timeout: 60_000 }).catch(() => undefined);
  await page.waitForTimeout(500);
}

test.describe("navigation and pages", () => {
  for (const p of PAGES) {
    test(`page ${p.path} renders as one unified page`, async ({ page }) => {
      const w = watch(page);
      await page.goto(p.path);
      await settle(page);
      if (p.key === "overview") await expect(page.getByRole("heading", { name: "LIFECYCLE", exact: true })).toBeVisible();
      else await expect(page.getByRole("heading", { level: 1, name: p.name })).toBeVisible();
      // grouped sidebar with exactly the 13 destinations
      const nav = page.getByRole("navigation", { name: "Main" });
      await expect(nav.locator("a[data-nav]")).toHaveCount(13);
      for (const g of ["Research Home", "Lifecycle & Portfolio Planning", "Markets & Risk Research", "Research Validation"]) {
        await expect(nav.getByRole("group", { name: g })).toBeAttached();
      }
      await expect(nav.locator(`a[data-nav="${p.path}"]`)).toHaveAttribute("aria-current", "page");
      const text = await page.locator("body").innerText();
      expect(text).not.toMatch(FORBIDDEN);
      if (p.sections.length) {
        await expect(page.locator("[data-section-tab]")).toHaveCount(p.sections.length);
        await expect(page.getByTestId("how-to-use")).toBeVisible();
      }
      // every plot sits inside a visualization frame, and every frame has an information button
      const orphanPlots = await page.locator(".js-plotly-plot").evaluateAll((els) => els.filter((e) => !e.closest("[data-viz-id]")).length);
      expect(orphanPlots).toBe(0);
      const frames = await page.locator("[data-viz-id]").count();
      expect(await page.locator("[data-viz-id] [data-viz-info]").count()).toBe(frames);
      expect(w.errors).toEqual([]);
      expect(w.launches).toEqual([]);
    });
  }
});

test("retired routes redirect and keep their query", async ({ page }) => {
  await page.goto("/lab");
  await expect(page).toHaveURL(/\/scenarios\?section=historical-analytics$/);
  await page.goto("/lab/fixed-income");
  await expect(page).toHaveURL(/\/fixed-income$/);
  await page.goto("/simulate?gamma=6");
  await expect(page).toHaveURL(/\/lifecycle-flows\?.*gamma=6/);
  await expect(page).toHaveURL(/section=simulator/);
  await expect(page.locator('[data-section-tab="simulator"]')).toHaveAttribute("aria-selected", "true");
});

test("homepage application guide links every page and answers research questions", async ({ page }) => {
  await page.goto("/");
  await settle(page);
  await expect(page.getByTestId("hero")).toContainText("Quantitative Portfolio Research Across Accumulation and Decumulation");
  for (const cta of ["Explore Withdrawal Risk", "Run a Portfolio Simulation", "Compare Strategies", "Explore Research Results"]) {
    await expect(page.getByRole("link", { name: new RegExp(cta) })).toBeVisible();
  }
  await expect(page.locator("[data-guide-card]")).toHaveCount(13);
  for (const p of PAGES.filter((x) => x.key !== "overview")) {
    await expect(page.locator(`[data-guide-link="${p.path}"]`)).toHaveAttribute("href", p.path);
  }
  for (const q of QUESTIONS) {
    await page.locator(`[data-question="${q.id}"]`).click();
    const start = page.locator(`[data-nav-start="${q.id}"]`);
    await expect(start).toHaveAttribute("href", new RegExp("^" + PAGES.find((p) => p.key === q.start.page)!.path.replace(/[/]/g, "\\/")));
  }
  await expect(page.getByTestId("journeys").locator("article")).toHaveCount(4);
  await page.locator('[data-guide-link="/permanent-portfolio"]').click();
  await expect(page).toHaveURL(/\/permanent-portfolio/);
});

test("information panel opens by keyboard, shows the registry explanation, and closes with Escape", async ({ page }) => {
  await page.goto("/withdrawal-lab?section=overview");
  await settle(page);
  const trigger = page.locator('[data-viz-info="WL-02"]');
  await expect(trigger).toBeVisible({ timeout: 60_000 });
  await trigger.focus();
  await page.keyboard.press("Enter");
  const body = page.locator('[data-viz-info-body="WL-02"]');
  await expect(body).toBeVisible();
  await expect(page.getByRole("dialog")).toContainText("A value of 40% means");
  for (const h of ["What this graph shows", "How to read it", "What is being calculated", "Why it matters", "How to interpret the result",
    "Assumptions and limitations", "Data provenance", "Related research"]) await expect(body).toContainText(h);
  await expect(body).toContainText(/Run\s*[0-9a-f]{6}/i);           // provenance comes from the persisted run
  await page.keyboard.press("Escape");
  await expect(body).toBeHidden();
  await expect(trigger).toBeFocused();
});

test("deep links select the section and scroll to the chart", async ({ page }) => {
  await page.goto("/withdrawal-lab?section=robustness#WL-06");
  await settle(page);
  await expect(page.locator('[data-section-tab="robustness"]')).toHaveAttribute("aria-selected", "true");
  await expect(page.locator('[data-viz-id="WL-06"]')).toBeInViewport({ timeout: 30_000 });
  await page.locator('[data-section-tab="outcomes"]').click();
  await expect(page).toHaveURL(/section=outcomes/);
  await expect(page.locator('[data-viz-id="WL-07"]')).toBeVisible({ timeout: 30_000 });
});

test("theme toggle switches light and dark", async ({ page }) => {
  await page.goto("/methodology?section=pipeline");
  const html = page.locator("html");
  const before = await html.getAttribute("class");
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await expect.poll(async () => (await html.getAttribute("class")) !== before).toBe(true);
});

test("derived-data export of a study chart downloads", async ({ page, request }) => {
  await page.goto("/rebalance?section=overview");
  const link = page.locator('[data-viz-id="RB-01"] a[aria-label="Export derived data (CSV)"]');
  await expect(link).toBeVisible({ timeout: 60_000 });
  const href = await link.getAttribute("href");
  expect(href).toMatch(/\/export\?format=csv/);
  const r = await request.get(href!);
  expect(r.status()).toBe(200);
});

/**
 * Every registered visualization, visited through its own deep link: it is either rendered (a frame with
 * that ID) or its section honestly says the study / input is not computed.
 */
test("every registered visualization is reachable from its deep link", async ({ page }) => {
  test.setTimeout(900_000);
  const bySection = new Map<string, string[]>();
  for (const v of VISUALIZATIONS) {
    const href = vizHref(v.id).split("#")[0];
    bySection.set(href, [...(bySection.get(href) ?? []), v.id]);
  }
  const missing: string[] = [];
  const notComputed: string[] = [];
  for (const [href, ids] of bySection) {
    await page.goto(href);
    await settle(page);
    await page.waitForTimeout(1500);
    const present = new Set(await page.locator("[data-viz-id]").evaluateAll((els) => els.map((e) => e.getAttribute("data-viz-id"))));
    const gated = await page.locator('[data-study-state="not-computed"]').count();
    for (const id of ids) {
      if (present.has(id)) continue;
      if (gated) notComputed.push(id); else missing.push(href + "#" + id);
    }
  }
  test.info().annotations.push({ type: "not-computed", description: notComputed.join(", ") || "none" });
  expect(missing).toEqual([]);
});

test.describe("research workflows", () => {
  test("1 · question navigator → withdrawal survival surface → path drilldown", async ({ page }) => {
    await page.goto("/");
    await page.locator('[data-question="bonds-useful"]').click();
    await page.locator('[data-nav-start="bonds-useful"]').click();
    await expect(page).toHaveURL(/withdrawal-lab\?section=overview/);
    await expect(page.locator('[data-viz-id="WL-01"]')).toBeVisible({ timeout: 60_000 });
    await page.locator('[data-section-tab="paths"]').click();
    await expect(page.locator('[data-viz-id="WL-11"] .js-plotly-plot').first()).toBeVisible({ timeout: 60_000 });
  });

  test("2 · Permanent Portfolio → Compare with 60/40 carries the selection", async ({ page }) => {
    await page.goto("/permanent-portfolio?section=overview");
    const box = page.getByTestId("compare-with-6040");
    await expect(box).toBeVisible({ timeout: 60_000 });
    await box.getByRole("button", { name: /Open in Strategy Comparison/ }).click();
    await expect(page).toHaveURL(/\/compare\?section=policies&policies=sixty_forty/);
    await expect(page.getByTestId("carried-policies")).toContainText("Permanent Portfolio");
    await expect(page.locator('[data-viz-id="CO-01"]')).toBeVisible({ timeout: 60_000 });
  });

  test("3 · study page → Run with current assumptions resolves to a cached or queued run", async ({ page }) => {
    await page.goto("/scenarios?section=stress");
    const btn = page.getByRole("button", { name: "Run with current assumptions" });
    await expect(btn).toBeVisible({ timeout: 60_000 });
    const resp = page.waitForResponse((r) => r.request().method() === "POST" && /\/v1\/studies\/scenario_lab/.test(r.url()));
    await btn.click();
    expect((await resp).status()).toBe(200);   // strict spec validation passed server-side
  });

  test("4 · runs registry → inspector → reproduce command with engine semantics", async ({ page }) => {
    await page.goto("/runs?section=registry");
    const first = page.locator('[data-viz-id="RN-01"] tbody button').first();
    await expect(first).toBeVisible({ timeout: 60_000 });
    await expect(page.locator('[data-viz-id="RN-01"]')).toContainText(/holdings_ledger|target_weight_kernel/);
    await first.click();
    await expect(page).toHaveURL(/id=/);
    await page.locator('[data-section-tab="reproduce"]').click();
    await expect(page.locator('[data-viz-id="RN-07"]')).toContainText("python -m lifecycle.cli reproduce", { timeout: 60_000 });
  });

  test("5 · market history analytics (absorbed lab) shows observed series", async ({ page }) => {
    await page.goto("/scenarios?section=historical-analytics");
    await expect(page.locator('[data-viz-id="SC-13"] table')).toBeVisible({ timeout: 60_000 });
    await page.locator('[data-section-tab="factors"]').click();
    await expect(page.locator('[data-viz-id="SC-25"]')).toBeVisible({ timeout: 60_000 });
  });

  test("6 · methodology visualization reference → open chart", async ({ page }) => {
    await page.goto("/methodology?section=visualizations");
    const ref = page.getByTestId("viz-reference");
    await ref.getByLabel("Filter visualizations").fill("FI-10");
    await ref.locator("#ref-FI-10").getByRole("link", { name: /Open chart/ }).click();
    await expect(page).toHaveURL(/fixed-income\?section=liabilities#FI-10/);
    await expect(page.locator('[data-viz-id="FI-10"]')).toBeVisible({ timeout: 60_000 });
  });
});
