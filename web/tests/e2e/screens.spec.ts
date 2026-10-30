import { expect, test } from "@playwright/test";

const SCREENS = [
  { path: "/", text: "How should an investor allocate" },
  { path: "/lab", text: "Multi-Asset Research Lab" },
  { path: "/simulate", text: "Lifecycle Simulator" },
  { path: "/optimize", text: "Utility & Policy Optimizer" },
  { path: "/withdrawal-lab", text: "Withdrawal-Rate Sensitivity Lab" },
  { path: "/compare", text: "Strategy Comparison & Validation" },
  { path: "/runs", text: "Runs & Reports" },
  { path: "/methodology", text: "Methodology" },
];

for (const s of SCREENS) {
  test(`renders ${s.path}`, async ({ page }) => {
    await page.goto(s.path);
    await expect(page.getByText(s.text).first()).toBeVisible();
    await page.waitForTimeout(1500);
    await expect(page).toHaveScreenshot(`${s.path === "/" ? "overview" : s.path.slice(1).replace(/\//g, "_")}.png`, {
      fullPage: true, maxDiffPixelRatio: 0.05, animations: "disabled",
    });
  });
}
