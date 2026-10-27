import { defineConfig, devices } from '@playwright/test';

const ci = !!process.env['CI'];
const capture = process.env['E2E_CAPTURE_ARTIFACTS'] === '1';
const external = process.env['E2E_EXTERNAL_SERVERS'] === '1';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1, // The local assistant deliberately serializes inference.
  forbidOnly: ci,
  retries: 0, // Preserve first-run failures instead of hiding flaky assertions.
  grepInvert: process.env['E2E_OLLAMA'] === '1' ? undefined : /@ollama/,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  outputDir: 'test-results',
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env['E2E_BASE_URL'] ?? 'http://localhost:4200',
    viewport: { width: 1440, height: 1000 },
    screenshot: capture ? 'only-on-failure' : 'off',
    trace: capture ? 'retain-on-failure' : 'off',
    video: capture ? 'retain-on-failure' : 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: process.env['E2E_BROWSER_CHANNEL'],
      },
    },
  ],
  // Backend/database lifecycle is explicit. Never start or seed a database implicitly.
  webServer: external
    ? undefined
    : {
        command: 'npm start -- --host localhost',
        url: 'http://localhost:4200',
        reuseExistingServer: !ci,
        timeout: 120_000,
      },
});
