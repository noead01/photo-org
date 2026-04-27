import { defineConfig, devices } from "@playwright/test";

const localBaseURL = "http://127.0.0.1:4173";
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? localBaseURL;
const forceLocalWebServer =
  process.env.PLAYWRIGHT_FORCE_LOCAL_WEBSERVER === "1" ||
  process.env.PLAYWRIGHT_FORCE_LOCAL_WEBSERVER === "true";
const shouldStartLocalWebServer = !process.env.PLAYWRIGHT_BASE_URL || forceLocalWebServer;
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 2 : undefined,
  reporter: isCI
    ? [
        ["github"],
        ["list"],
        ["html", { open: "never" }],
      ]
    : [
        ["list"],
        ["html", { open: "never" }],
      ],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: shouldStartLocalWebServer
    ? {
        command: "npm run dev -- --host 127.0.0.1 --port 4173",
        reuseExistingServer: !isCI,
        timeout: 120_000,
        url: localBaseURL,
      }
    : undefined,
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
