import { existsSync } from "node:fs";
import { defineConfig } from "@playwright/test";

// End-to-end tests of the unified application. Needs the API on :8000 (make api) with persisted study runs
// (python -m lifecycle.cli seed-v2) for the figure checks; pages without runs must show "not computed".
const PREINSTALLED = "/opt/pw-browsers/chromium";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 180_000,
  workers: 2,
  use: {
    baseURL: process.env.WEB_URL ?? "http://localhost:3000",
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    launchOptions: existsSync(PREINSTALLED) && !process.env.PW_BUNDLED ? { executablePath: PREINSTALLED } : {},
  },
  webServer: process.env.WEB_URL ? undefined : { command: "npm run start", port: 3000, reuseExistingServer: true },
});
