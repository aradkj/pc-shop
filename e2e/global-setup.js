import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

export default async function globalSetup() {
  if (process.env.NO_SEED) {
    return;
  }
  const isWindows = process.platform === 'win32';
  const venvPython = isWindows
    ? path.join(rootDir, 'backend', '.venv', 'Scripts', 'python.exe')
    : path.join(rootDir, 'backend', '.venv', 'bin', 'python3');
  const pyCmd = fs.existsSync(venvPython) ? `"${venvPython}"` : (isWindows ? 'python' : 'python3');
  const port = process.env.POSTGRES_PORT || (isWindows ? '5433' : '5432');
  const dbUrl = process.env.DATABASE_URL || `postgresql+psycopg://arad_user:change-me-db-password@127.0.0.1:${port}/arad_store_test`;

  console.log(`Seeding test database for E2E tests at ${dbUrl}...`);
  try {
    execSync(`${pyCmd} -m app.seed`, {
      cwd: path.join(rootDir, 'backend'),
      env: {
        ...process.env,
        DATABASE_URL: dbUrl,
        APP_ENV: 'test',
        SEED_ADMIN_PASSWORD: process.env.SEED_ADMIN_PASSWORD || 'Admin12345!',
        SEED_CUSTOMER_PASSWORD: process.env.SEED_CUSTOMER_PASSWORD || 'Customer12345!',
      },
      stdio: 'inherit',
    });
  } catch (err) {
    console.error('CRITICAL: Required database seed failed in Playwright globalSetup:', err.message);
    throw err;
  }
}
