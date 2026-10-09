import { test, expect } from '@playwright/test';

test.describe('Catalog and Product Flow Verification', () => {
  test('Home page displays 8 categories and new arrival products', async ({ page }) => {
    await page.goto('/index.html');
    await expect(page.locator('#home-categories .category-card')).toHaveCount(8);
    const categoryNames = await page.locator('#home-categories .category-card strong').allTextContents();
    expect(categoryNames.sort()).toEqual([
      'CPU',
      'Cooler',
      'GPU',
      'Motherboard',
      'PC Case',
      'PSU',
      'RAM',
      'Storage',
    ].sort());

    await expect(page.locator('#home-products .product-card')).toHaveCount(8);
    await page.screenshot({ path: 'test-results/homepage.png', fullPage: true });
  });

  test('Shop page displays products, pagination, and filters all 8 categories', async ({ page }) => {
    await page.goto('/pages/products.html');

    // The category options are appended after /categories resolves, so wait for them
    // before reading; "All categories" is the static first option.
    await expect(page.locator('#filter-category option')).toHaveCount(9);
    const selectOptions = await page.locator('#filter-category option').allInnerTexts();
    expect(selectOptions).toContain('CPU');
    expect(selectOptions).toContain('GPU');
    expect(selectOptions).toContain('RAM');
    expect(selectOptions).toContain('Motherboard');
    expect(selectOptions).toContain('Storage');
    expect(selectOptions).toContain('PSU');
    expect(selectOptions).toContain('PC Case');
    expect(selectOptions).toContain('Cooler');

    // Verify initial products load
    await expect(page.locator('.product-card')).toHaveCount(12);
    await expect(page.locator('#results-summary')).toContainText('of 80 products');

    // Test category filter for CPU (exactly 10 products)
    await page.selectOption('#filter-category', { label: 'CPU' });
    await page.click('button[type="submit"]');
    await expect(page.locator('.product-card')).toHaveCount(10);
    await expect(page.locator('#results-summary')).toContainText('10 of 10 products');
    await page.screenshot({ path: 'test-results/shop-cpu.png', fullPage: true });

    // Test category filter for GPU (exactly 10 products)
    await page.selectOption('#filter-category', { label: 'GPU' });
    await page.click('button[type="submit"]');
    await expect(page.locator('.product-card')).toHaveCount(10);

    // Test category filter for Cooler (exactly 10 products)
    await page.selectOption('#filter-category', { label: 'Cooler' });
    await page.click('button[type="submit"]');
    await expect(page.locator('.product-card')).toHaveCount(10);
  });

  test('Product detail page renders specs, price, stock, and image', async ({ page }) => {
    await page.goto('/pages/product.html?slug=amd-ryzen-7-7800x3d');

    await expect(page.locator('h1')).toHaveText('AMD Ryzen 7 7800X3D');
    await expect(page.locator('.product-detail__price')).toHaveText('$399.00');
    await expect(page.locator('.stock')).toContainText('In stock');
    await expect(page.locator('.product-detail__media img')).toBeVisible();

    // Verify specifications table
    await expect(page.locator('.product-specs h2')).toHaveText('Technical Specifications');
    const specsText = await page.locator('.specs-list').innerText();
    expect(specsText).toContain('Socket');
    expect(specsText).toContain('AM5');
    expect(specsText).toContain('Cores');
    expect(specsText).toContain('8');
    expect(specsText).toContain('Threads');
    expect(specsText).toContain('16');
    expect(specsText).toContain('Base Clock');
    expect(specsText).toContain('4.2 GHz');
    expect(specsText).toContain('Boost Clock');
    expect(specsText).toContain('5.0 GHz');

    await page.screenshot({ path: 'test-results/product-detail.png', fullPage: true });
  });
});
