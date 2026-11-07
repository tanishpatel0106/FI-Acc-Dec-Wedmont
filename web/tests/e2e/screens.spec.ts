import { expect, test } from "@playwright/test";

// v2 pages A-M plus the retained v1 routes. Needs `make api` with a built panel (and ideally `seed-v2`).
const SCREENS = [
  { path: "/", text: "Research command center (v2)", ids: ["OV-01", "OV-06", "OV-07", "OV-08"] },
  { path: "/withdrawal-lab", text: "Bond Necessity & Sustainable Spending", ids: [] },
  { path: "/lifecycle-flows", text: "Signed Contributions", ids: [] },
  { path: "/permanent-portfolio", text: "Permanent Portfolio Research Laboratory", ids: [] },
  { path: "/rebalance", text: "Rebalancing & Cash-Flow Execution Laboratory", ids: [] },
  { path: "/fixed-income", text: "Rates, Liability Matching & Credit Research", ids: ["FI-01", "FI-04", "FI-14"] },
  { path: "/market-state", text: "Public-Data As-of Terminal", ids: ["MS-01", "MS-02", "MS-12"] },
  { path: "/scenarios", text: "Scenario, Dependence & Stress Research", ids: [] },
  { path: "/optimize", text: "Multi-Objective Allocation & Policy Surfaces", ids: [] },
  { path: "/compare", text: "Policy & Historical Cohort Comparison", ids: [] },
  { path: "/research", text: "Hypotheses, Validation & Statistical Workbench", ids: [] },
  { path: "/runs", text: "Reproduction, Diagnostics & Reports", ids: ["RN-01", "RN-04", "RN-10"] },
  { path: "/methodology", text: "Mathematical & Data Methodology", ids: ["MT-01", "MT-02", "MT-07"] },
  { path: "/lab", text: "Multi-Asset Research Lab", ids: [] },
  { path: "/simulate", text: "Lifecycle Simulator", ids: [] },
];

for (const s of SCREENS) {
  test(`renders ${s.path}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(s.path);
    await expect(page.getByText(s.text).first()).toBeVisible();
    for (const id of s.ids) await expect(page.locator("section#" + id)).toBeVisible({ timeout: 30_000 });
    await page.waitForTimeout(1500);
    expect(errors).toEqual([]);
    await expect(page).toHaveScreenshot(`${s.path === "/" ? "overview" : s.path.slice(1).replace(/\//g, "_")}.png`, {
      fullPage: true, maxDiffPixelRatio: 0.05, animations: "disabled",
    });
  });
}
