import { defineConfig, devices } from '@playwright/test';

const chrome = process.env.WHYFINDER_CHROME; // local runs can point at an installed Chrome
export default defineConfig({
  testDir: 'tests/e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: 'http://localhost:4173/whyfinder/',
    trace: 'retain-on-failure',
    launchOptions: chrome ? { executablePath: chrome } : {},
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    { name: 'phone', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: 'npm run build && npm run preview -- --port 4173 --strictPort',
    url: 'http://localhost:4173/whyfinder/',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
