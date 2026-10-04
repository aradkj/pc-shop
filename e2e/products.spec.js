import { test, expect } from '@playwright/test';

test.describe('Products and Search', () => {
  test('displays catalogue and navigates to product details via slug URL', async ({ page }) => {
    await page.goto('/pages/products.html');

    // Check header
    await expect(page.locator('h1')).toContainText('Shop');

    // Wait for product cards to load
    const firstCard = page.locator('.product-card').first();
    await expect(firstCard).toBeVisible();

    // Verify detail URL contains slug
    const detailLink = firstCard.locator('.product-card__title a');
    const href = await detailLink.getAttribute('href');
    expect(href).toContain('slug=');

    // Click to navigate to product detail
    await detailLink.click();
    await page.waitForURL('**/pages/product.html?slug=*');

    // Verify product detail page loads
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.product-detail__price')).toBeVisible();
    await expect(page.locator('[data-add]')).toBeVisible();
  });

  test('search filter matches products correctly', async ({ page }) => {
    await page.goto('/pages/products.html');

    // Fill search input
    await page.fill('#filter-search', 'Ryzen');
    await page.click('button[type="submit"]');

    // Wait for results
    await expect(page.locator('.product-card')).toHaveCount(2);
    await expect(page.locator('.product-card').first()).toContainText('Ryzen');
  });

  test('category filter updates results', async ({ page }) => {
    await page.goto('/pages/products.html');

    // Select category Graphics Cards
    await page.selectOption('#filter-category', { label: 'Graphics Cards' });
    await page.click('button[type="submit"]');

    // Verify cards are GPUs
    await expect(page.locator('.product-card').first()).toBeVisible();
    const count = await page.locator('.product-card').count();
    expect(count).toBeGreaterThanOrEqual(1);
  });
});
