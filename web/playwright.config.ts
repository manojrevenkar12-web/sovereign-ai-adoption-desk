import { defineConfig, devices } from "@playwright/test";

// Runs the console against the real desk API and PostgreSQL (seeded with the fictional portfolio).
const env = {
  DESK_DATABASE_URL: process.env.DESK_DATABASE_URL ?? "postgresql://postgres@127.0.0.1:5432/desk",
  DESK_AUTH: "dev",
  DESK_TODAY: "2026-10-28",
  DESK_SIGNING_KEY: process.env.DESK_SIGNING_KEY ?? "",
};

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 0,
  workers: 1,
  globalSetup: "./e2e/global-setup.ts",
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],
  use: { baseURL: "http://localhost:5173", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "phone", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "../.venv/bin/desk serve --port 8080",
      url: "http://localhost:8080/healthz",
      reuseExistingServer: !process.env.CI,
      env,
    },
    {
      command: "npm run preview",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      env: { DESK_API_URL: "http://localhost:8080" },
    },
  ],
});
