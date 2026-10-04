import { test, expect } from '@playwright/test';

test.describe('Checkout and Order Flow', () => {
  test('customer can add items, checkout, and view order in orders list', async ({ page }) => {
    // 1. Log in as Bob
    await page.goto('/pages/login.html');
    await page.fill('#identifier', 'bob@example.com');
    await page.fill('#password', 'Customer12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');

    // 2. Open products and add item to cart
    await page.goto('/pages/products.html');
    const firstCard = page.locator('.product-card').first();
    await firstCard.locator('.product-card__title a').click();
    await page.waitForURL('**/pages/product.html?slug=*');
    await page.click('[data-add]');
    await expect(page.locator('.toast')).toBeVisible();

    // 3. Go to Cart
    await page.goto('/pages/cart.html');
    const checkoutBtn = page.locator('[data-checkout]');
    await expect(checkoutBtn).toBeVisible();

    // 4. Place order
    await checkoutBtn.click();

    // 5. Order confirmation appears
    await expect(page.locator('.confirmation')).toBeVisible();
    await expect(page.locator('.confirmation h2')).toContainText('Thank you!');

    // 6. Navigate to orders page via confirmation button
    await page.click('a:has-text("View my orders")');
    await page.waitForURL('**/pages/orders.html*');
    await expect(page.locator('h1')).toContainText('My orders');
    await expect(page.locator('.order-card').first()).toBeVisible();

  });
});
