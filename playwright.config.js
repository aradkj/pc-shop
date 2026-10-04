import { defineConfig, devices } from '@playwright/test';

import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const isWindows = process.platform === 'win32';
const venvPython = isWindows
  ? path.join(__dirname, 'backend', '.venv', 'Scripts', 'python.exe')
  : path.join(__dirname, 'backend', '.venv', 'bin', 'python3');
const pyCmd = fs.existsSync(venvPython) ? `"${venvPython}"` : (isWindows ? 'python' : 'python3');
const defaultDbPort = process.env.POSTGRES_PORT || (isWindows ? '5433' : '5432');

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.js',
  timeout: 45000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false, // run sequentially to prevent database conflicts between tests
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results/',
  use: {
    baseURL: 'http://localhost:5500',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: process.env.NO_WEBSERVER ? undefined : [
    {
      command: `${pyCmd} -m http.server 5500 --directory frontend`,
      url: 'http://localhost:5500/index.html',
      reuseExistingServer: !process.env.CI,
      timeout: 15000,
    },
    {
      command: `cd backend && ${pyCmd} -m uvicorn app.main:app --port 8000`,
      url: 'http://localhost:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 20000,
      env: {
        APP_ENV: 'test',
        DATABASE_URL: process.env.DATABASE_URL || `postgresql+psycopg://arad_user:change-me-db-password@127.0.0.1:${defaultDbPort}/arad_store_test`,
        SECRET_KEY: 'test-secret-key-1234567890-playwright-tests-e2e',
        CORS_ORIGINS: 'http://localhost:5500,http://127.0.0.1:5500',
        COOKIE_SECURE: 'false',
        BCRYPT_ROUNDS: '4',
      },
    },
  ],
});
