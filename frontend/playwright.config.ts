import { defineConfig, devices } from "@playwright/test";

// End-to-end: the real API (with a fake LLM, scripts/e2e_server.py) and a production build of the app.
const API_PORT = 8020;
const APP_PORT = 3100;
const python = process.env.E2E_PYTHON ?? "../backend/.venv/bin/python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${APP_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} ../scripts/e2e_server.py --port ${API_PORT}`,
      url: `http://localhost:${API_PORT}/health`,
      env: { FRONTEND_ORIGIN: `http://localhost:${APP_PORT}` },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `npm run build && npx next start -p ${APP_PORT}`,
      url: `http://localhost:${APP_PORT}`,
      env: { NEXT_PUBLIC_API_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
    },
  ],
});
