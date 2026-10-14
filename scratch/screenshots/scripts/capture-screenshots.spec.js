import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const outDir = path.resolve('scratch', 'screenshots');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

test.describe('Visual Screenshots & Responsiveness Suite', () => {
  const viewports = [
    { name: 'desktop', width: 1440, height: 900 },
    { name: 'laptop', width: 1280, height: 800 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'mobile', width: 390, height: 844 },
    { name: 'narrow-mobile', width: 320, height: 700 },
  ];

  for (const vp of viewports) {
    test(`captures homepage at ${vp.name} (${vp.width}x${vp.height}) without overflow`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/index.html');
      await page.waitForLoadState('networkidle');

      // Verify no horizontal overflow
      const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(hasOverflow).toBeFalsy();

      await page.screenshot({ path: path.join(outDir, `homepage-${vp.name}.png`), fullPage: false });
    });

    test(`captures pc-builder at ${vp.name} (${vp.width}x${vp.height}) without overflow`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/pages/pc-builder.html');
      await page.waitForLoadState('networkidle');

      const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(hasOverflow).toBeFalsy();

      await page.screenshot({ path: path.join(outDir, `pc-builder-${vp.name}.png`), fullPage: false });
    });
  }

  test('captures key store pages at desktop 1440x900', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });

    // Shop catalogue
    await page.goto('/pages/products.html');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(outDir, 'shop-catalogue-desktop.png') });

    // Product detail
    await page.goto('/pages/product.html?slug=amd-ryzen-7-7800x3d');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(outDir, 'product-detail-desktop.png') });

    // Login page
    await page.goto('/pages/login.html');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(outDir, 'login-desktop.png') });

    // Admin dashboard (log in first)
    await page.fill('#identifier', 'admin@example.com');
    await page.fill('#password', 'Admin12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');

    await page.goto('/pages/admin.html');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(outDir, 'admin-dashboard-desktop.png') });

    // Profile page
    await page.goto('/pages/profile.html');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(outDir, 'profile-desktop.png') });

    // Cart page
    await page.goto('/pages/cart.html');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: path.join(outDir, 'cart-desktop.png') });
  });
});
