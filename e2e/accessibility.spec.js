import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility Audits (axe-core)', () => {
  test('homepage passes accessibility checks', async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('login page passes accessibility checks', async ({ page }) => {
    await page.goto('/pages/login.html');
    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('register page passes accessibility checks', async ({ page }) => {
    await page.goto('/pages/register.html');
    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('product page passes accessibility checks', async ({ page }) => {
    await page.goto('/pages/product.html?slug=amd-ryzen-7-7800x3d');
    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('cart page passes accessibility checks', async ({ page }) => {
    await page.goto('/pages/cart.html');
    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('admin page passes accessibility checks', async ({ page }) => {
    // Log in as admin first
    await page.goto('/pages/login.html');
    await page.fill('#identifier', 'admin@example.com');
    await page.fill('#password', 'Admin12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');

    await page.goto('/pages/admin.html');
    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('pc builder page passes accessibility checks', async ({ page }) => {
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');
    const accessibilityScanResults = await new AxeBuilder({ page })
      .analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });
});
