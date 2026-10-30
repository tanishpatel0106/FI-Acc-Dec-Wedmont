import { defineConfig } from "@playwright/test";

// End-to-end + visual snapshots of the five research screens. Needs the API on :8000 (make api).
export default defineConfig({
  testDir: "tests/e2e",
  timeout: 120_000,
  use: { baseURL: process.env.WEB_URL ?? "http://localhost:3000", viewport: { width: 1440, height: 1000 } },
  webServer: process.env.WEB_URL ? undefined : { command: "npm run start", port: 3000, reuseExistingServer: true },
});
