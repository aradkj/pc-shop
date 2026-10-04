import { test, expect } from '@playwright/test';

test.describe('Admin Panel', () => {
  test('admin can view dashboard, search orders, and see audit logs', async ({ page }) => {
    // 1. Log in as admin
    await page.goto('/pages/login.html');
    await page.fill('#identifier', 'admin@example.com');
    await page.fill('#password', 'Admin12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');

    // 2. Navigate to Admin page
    await page.goto('/pages/admin.html');
    await expect(page.locator('.stat-grid')).toBeVisible();
    await expect(page.locator('.stat-card').first()).toBeVisible();

    // 3. Navigate to Orders section
    await page.click('a[href="#orders"]');
    await expect(page.locator('#admin-order-search')).toBeVisible();

    // Verify order list shows order numbers
    const firstRow = page.locator('tbody tr').first();
    await expect(firstRow).toBeVisible();
    await expect(firstRow).toContainText('ORD-');


    // Test search filter
    await page.fill('#admin-order-search', 'alice');
    await page.waitForTimeout(400); // debounce
    await expect(page.locator('tbody tr').first()).toContainText('alice@example.com');

    // 4. Navigate to Audit Logs section
    await page.click('a[href="#audit"]');
    await expect(page.locator('#admin-audit-action')).toBeVisible();
    await expect(page.locator('#admin-audit-entity')).toBeVisible();
    await expect(page.locator('[data-list]')).toBeVisible();
  });
});

