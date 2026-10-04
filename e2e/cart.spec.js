import { test, expect } from '@playwright/test';

test.describe('Cart Flow', () => {
  test('customer can add product to cart, update quantity, and remove item', async ({ page }) => {
    // 1. Log in as Alice
    await page.goto('/pages/login.html');
    await page.fill('#identifier', 'alice@example.com');
    await page.fill('#password', 'Customer12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');

    // 2. Open products page and click on a product
    await page.goto('/pages/products.html');
    const firstCard = page.locator('.product-card').first();
    await firstCard.locator('.product-card__title a').click();
    await page.waitForURL('**/pages/product.html?slug=*');

    // 3. Add to cart
    await page.click('[data-add]');
    await expect(page.locator('.toast')).toBeVisible();

    // 4. Check cart badge
    await expect(page.locator('[data-cart-count]')).toBeVisible();

    // 5. Open Cart page
    await page.goto('/pages/cart.html');
    await expect(page.locator('h1')).toContainText('Your cart');

    const cartItem = page.locator('.cart-item').first();

    await expect(cartItem).toBeVisible();

    // 6. Increase quantity
    const plusBtn = cartItem.locator('[data-qty-step="1"]');
    await plusBtn.click();
    await page.waitForTimeout(500); // allow debounce / API update

    // 7. Remove item
    const removeBtn = cartItem.locator('[data-remove]');
    await removeBtn.click();
    await expect(page.locator('text=Your cart is empty')).toBeVisible();
  });
});
