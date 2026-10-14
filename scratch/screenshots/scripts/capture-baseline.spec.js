import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const outDir = path.resolve('scratch', 'screenshots', 'baseline');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

const viewports = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'narrow-mobile', width: 320, height: 700 },
];

test.describe('Baseline Screenshot Suite', () => {
  for (const vp of viewports) {
    test(`captures unauthenticated pages at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });

      // 1. Homepage
      await page.goto('/index.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `homepage-${vp.name}.png`), fullPage: false });

      // 2. Catalogue
      await page.goto('/pages/products.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `catalogue-${vp.name}.png`), fullPage: false });

      // 3. Product detail
      await page.goto('/pages/product.html?slug=amd-ryzen-7-7800x3d');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `product-detail-${vp.name}.png`), fullPage: false });

      // 4. PC Builder
      await page.goto('/pages/pc-builder.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `pc-builder-${vp.name}.png`), fullPage: false });

      // 5. Cart
      await page.goto('/pages/cart.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `cart-${vp.name}.png`), fullPage: false });

      // 6. Login
      await page.goto('/pages/login.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `login-${vp.name}.png`), fullPage: false });

      // 7. 404
      await page.goto('/pages/404.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `404-${vp.name}.png`), fullPage: false });
    });

    test(`captures customer authenticated pages (profile, orders) at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/pages/login.html');
      await page.fill('#identifier', 'alice@example.com');
      await page.fill('#password', 'Customer12345!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/index.html*');

      // Profile
      await page.goto('/pages/profile.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `profile-${vp.name}.png`), fullPage: false });

      // Orders
      await page.goto('/pages/orders.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `orders-${vp.name}.png`), fullPage: false });
    });

    test(`captures admin dashboard at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/pages/login.html');
      await page.fill('#identifier', 'admin@example.com');
      await page.fill('#password', 'Admin12345!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/index.html*');

      // Admin
      await page.goto('/pages/admin.html');
      await page.waitForLoadState('networkidle');
      await page.screenshot({ path: path.join(outDir, `admin-${vp.name}.png`), fullPage: false });
    });
  }
});
