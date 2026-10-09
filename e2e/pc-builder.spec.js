import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('PC Builder Flow', () => {
  test('homepage hero links to PC builder and navigation works', async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    // Hero banner button check
    const heroBtn = page.locator('a[href="pages/pc-builder.html"]');
    await expect(heroBtn).toBeVisible();
    await heroBtn.click();
    await page.waitForURL('**/pages/pc-builder.html*');

    await expect(page.locator('h1')).toContainText('Build Your Own PC');
  });

  test('configurator renders 8 steps, initial empty summary, and disabled add button', async ({ page }) => {
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');

    // 8 category steps
    const steps = page.locator('.builder-step');
    await expect(steps).toHaveCount(8);

    // Initial summary
    const summary = page.locator('[data-build-summary]');
    await expect(summary).toBeVisible();
    await expect(summary).toContainText('0 of 8 components');
    await expect(page.locator('[data-summary-subtotal]')).toHaveText('$0.00');
    await expect(page.locator('[data-summary-discount]')).toHaveText('-$0.00');
    await expect(page.locator('[data-summary-total]')).toHaveText('$0.00');

    // Promotional banner explains how to unlock 5% discount
    await expect(page.locator('[data-discount-banner]')).toContainText('Get 5% Off Your Build');

    // Add to cart button is disabled
    const addBtn = page.locator('[data-action="add-build-to-cart"]');
    await expect(addBtn).toBeDisabled();
  });

  test('filters components and shows real-time live pricing on selection', async ({ page }) => {
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');

    // CPU picker should be open by default
    const cpuSearch = page.locator('input[data-search-slot="cpu"]');
    await expect(cpuSearch).toBeVisible();

    // Filter CPU by name
    await cpuSearch.fill('7800X3D');
    const cpuCards = page.locator('[data-picker-slot="cpu"] [data-product-card]:visible');
    await expect(cpuCards).toHaveCount(1);
    await expect(cpuCards.first()).toContainText('AMD Ryzen 7 7800X3D');

    // Select the CPU
    const selectBtn = cpuCards.first().locator('[data-action="select-product"]');
    await expect(selectBtn).toBeEnabled();
    await selectBtn.click();

    // CPU step should now show selected box
    const selectedCpu = page.locator('[data-selected-slot="cpu"]');
    await expect(selectedCpu).toBeVisible();
    await expect(selectedCpu).toContainText('AMD Ryzen 7 7800X3D');

    // Summary updates to 1 component and reflects price
    await expect(page.locator('[data-build-summary]')).toContainText('1 of 8 components');
    await expect(page.locator('[data-summary-subtotal]')).toHaveText('$399.00');
    // Discount is 0 for incomplete build
    await expect(page.locator('[data-summary-discount]')).toHaveText('-$0.00');
    await expect(page.locator('[data-summary-total]')).toHaveText('$399.00');
  });

  test('detects socket mismatch incompatibility with AM4/Intel motherboards', async ({ page }) => {
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');

    // Select AM5 CPU: 7800X3D
    const cpuSearch = page.locator('input[data-search-slot="cpu"]');
    await cpuSearch.fill('7800X3D');
    await page.locator('[data-picker-slot="cpu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // Open Motherboard slot
    const moboChooseBtn = page.locator('[data-choose-slot="motherboard"]');
    await moboChooseBtn.click();

    // Motherboards for Intel or AM4 should show Incompatible badge
    const moboPicker = page.locator('[data-picker-slot="motherboard"]');
    await expect(moboPicker).toBeVisible();

    const moboSearch = page.locator('input[data-search-slot="motherboard"]');
    await moboSearch.fill('B550'); // AM4 motherboard
    const am4Card = moboPicker.locator('[data-product-card]:visible').first();
    await expect(am4Card).toBeVisible();
    await expect(am4Card.locator('[data-compat-status="incompatible"]')).toBeVisible();
    await expect(am4Card.locator('[data-recommendation-reason]')).toContainText('Socket mismatch');

    // If customer selects the incompatible motherboard anyway, backend validation displays issues in summary
    await am4Card.locator('[data-action="select-product"]').click();
    await expect(page.locator('[data-validation-issues]')).toBeVisible();
    await expect(page.locator('[data-validation-issues]')).toContainText('does not match Motherboard socket');
  });

  test('displays GPU recommendations and reasons based on CPU choice', async ({ page }) => {
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');

    // Select Ryzen 7 7800X3D
    const cpuSearch = page.locator('input[data-search-slot="cpu"]');
    await cpuSearch.fill('7800X3D');
    await page.locator('[data-picker-slot="cpu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // Open GPU slot
    await page.locator('[data-choose-slot="gpu"]').click();
    const gpuPicker = page.locator('[data-picker-slot="gpu"]');
    await expect(gpuPicker).toBeVisible();

    // Check that GPU cards show recommendation badges with reasons
    const recBadge = gpuPicker.locator('[data-compat-status="recommended"]').first();
    await expect(recBadge).toBeVisible();
    const recReason = gpuPicker.locator('[data-recommendation-reason]').first();
    await expect(recReason).toBeVisible();
  });

  test('unlocks authoritative 5% discount when all 8 components are selected and compatible', async ({ page }) => {
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');

    // 1. CPU: AMD Ryzen 7 7800X3D ($399.00)
    await page.locator('input[data-search-slot="cpu"]').fill('7800X3D');
    await page.locator('[data-picker-slot="cpu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 2. Motherboard: MSI B650 GAMING PLUS WIFI ($169.99)
    await page.locator('[data-choose-slot="motherboard"]').click();
    await page.locator('input[data-search-slot="motherboard"]').fill('MSI B650 GAMING PLUS');
    await page.locator('[data-picker-slot="motherboard"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 3. RAM: G.Skill Trident Z5 Neo RGB 32GB ($114.99)
    await page.locator('[data-choose-slot="ram"]').click();
    await page.locator('input[data-search-slot="ram"]').fill('Trident Z5 Neo');
    await page.locator('[data-picker-slot="ram"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 4. GPU: Gigabyte GeForce RTX 4060 ($299.99)
    await page.locator('[data-choose-slot="gpu"]').click();
    await page.locator('input[data-search-slot="gpu"]').fill('RTX 4060 Windforce');
    await page.locator('[data-picker-slot="gpu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 5. Storage: Kingston NV2 1TB NVMe ($61.99)
    await page.locator('[data-choose-slot="storage"]').click();
    await page.locator('input[data-search-slot="storage"]').fill('Kingston NV2 1TB');
    await page.locator('[data-picker-slot="storage"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 6. PSU: Cooler Master MWE Gold 750 V2 ($99.99)
    await page.locator('[data-choose-slot="psu"]').click();
    await page.locator('input[data-search-slot="psu"]').fill('MWE Gold 750');
    await page.locator('[data-picker-slot="psu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 7. PC Case: Montech AIR 903 BASE Black ($65.99)
    await page.locator('[data-choose-slot="pc-case"]').click();
    await page.locator('input[data-search-slot="pc-case"]').fill('AIR 903 BASE');
    await page.locator('[data-picker-slot="pc-case"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 8. Cooler: Thermalright Peerless Assassin 120 SE ($34.99)
    await page.locator('[data-choose-slot="cooler"]').click();
    await page.locator('input[data-search-slot="cooler"]').fill('Peerless Assassin');
    await page.locator('[data-picker-slot="cooler"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // Verify 8 of 8 selected
    const summary = page.locator('[data-build-summary]');
    await expect(summary).toContainText('8 of 8 components');

    // Verify discount banner unlocked
    const banner = page.locator('[data-discount-banner]');
    await expect(banner).toHaveClass(/is-unlocked/);
    await expect(banner).toContainText('Complete Build!');
    await expect(banner).toContainText('5% Build Your Own PC discount unlocked');

    // Expected prices:
    // Subtotal: 399.00 + 169.99 + 114.99 + 299.99 + 61.99 + 99.99 + 65.99 + 34.99 = 1246.93
    // Discount 5%: 1246.93 * 0.05 = 62.3465 -> 62.35
    // Total: 1246.93 - 62.35 = 1184.58
    await expect(page.locator('[data-summary-subtotal]')).toHaveText('$1,246.93');
    await expect(page.locator('[data-summary-discount]')).toHaveText('-$62.35');
    await expect(page.locator('[data-summary-total]')).toHaveText('$1,184.58');

    // Add to cart button is now enabled
    const addBtn = page.locator('[data-action="add-build-to-cart"]');
    await expect(addBtn).toBeEnabled();
  });

  test('authenticated customer can add complete build to cart with discount and see in cart', async ({ page }) => {
    // 1. Log in as Alice first
    await page.goto('/pages/login.html');
    await page.fill('#identifier', 'alice@example.com');
    await page.fill('#password', 'Customer12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');

    // 2. Go to PC Builder
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');

    // 3. Select all 8 components
    await page.locator('input[data-search-slot="cpu"]').fill('7800X3D');
    await page.locator('[data-picker-slot="cpu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    await page.locator('[data-choose-slot="motherboard"]').click();
    await page.locator('input[data-search-slot="motherboard"]').fill('MSI B650 GAMING PLUS');
    await page.locator('[data-picker-slot="motherboard"] [data-product-card]:visible [data-action="select-product"]').first().click();

    await page.locator('[data-choose-slot="ram"]').click();
    await page.locator('input[data-search-slot="ram"]').fill('Trident Z5 Neo');
    await page.locator('[data-picker-slot="ram"] [data-product-card]:visible [data-action="select-product"]').first().click();

    await page.locator('[data-choose-slot="gpu"]').click();
    await page.locator('input[data-search-slot="gpu"]').fill('RTX 4060 Windforce');
    await page.locator('[data-picker-slot="gpu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    await page.locator('[data-choose-slot="storage"]').click();
    await page.locator('input[data-search-slot="storage"]').fill('Kingston NV2 1TB');
    await page.locator('[data-picker-slot="storage"] [data-product-card]:visible [data-action="select-product"]').first().click();

    await page.locator('[data-choose-slot="psu"]').click();
    await page.locator('input[data-search-slot="psu"]').fill('MWE Gold 750');
    await page.locator('[data-picker-slot="psu"] [data-product-card]:visible [data-action="select-product"]').first().click();

    await page.locator('[data-choose-slot="pc-case"]').click();
    await page.locator('input[data-search-slot="pc-case"]').fill('AIR 903 BASE');
    await page.locator('[data-picker-slot="pc-case"] [data-product-card]:visible [data-action="select-product"]').first().click();

    await page.locator('[data-choose-slot="cooler"]').click();
    await page.locator('input[data-search-slot="cooler"]').fill('Peerless Assassin');
    await page.locator('[data-picker-slot="cooler"] [data-product-card]:visible [data-action="select-product"]').first().click();

    // 4. Click Add Complete Build to Cart
    const addBtn = page.locator('[data-action="add-build-to-cart"]');
    await expect(addBtn).toBeEnabled();
    await addBtn.click();

    // 5. Success modal appears with 5% discount breakdown
    const modal = page.locator('.modal');
    await expect(modal).toBeVisible();
    await expect(modal.locator('h2')).toContainText('Build Added to Cart!');
    await expect(modal).toContainText('5% Build Discount:');
    await expect(modal).toContainText('-$62.35');

    // 6. Navigate to cart page
    await modal.locator('a[href*="cart.html"]').click();
    await page.waitForURL('**/pages/cart.html*');

    // 7. Cart shows items
    const cartItems = page.locator('.cart-item');
    await expect(cartItems).toHaveCount(8);

    // 8. Place order and verify discounted total on confirmation ($1,184.58)
    await page.click('[data-checkout]');
    await expect(page.locator('.confirmation')).toBeVisible();
    await expect(page.locator('.confirmation h2')).toContainText('Thank you!');
    await expect(page.locator('.confirmation')).toContainText('$1,184.58');
  });

  test('passes axe-core accessibility checks', async ({ page }) => {
    await page.goto('/pages/pc-builder.html');
    await page.waitForLoadState('networkidle');

    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();
    expect(accessibilityScanResults.violations).toEqual([]);
  });
});
