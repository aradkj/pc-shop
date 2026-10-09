import { test, expect } from '@playwright/test';

/**
 * Product images end-to-end: every card renders one, a missing or broken
 * `image_url` falls back to the placeholder, and nothing shifts while loading.
 */
test.describe('Product images', () => {
  test('shop cards render a loaded image inside a fixed-ratio media box', async ({ page }) => {
    await page.goto('/pages/products.html');
    await expect(page.locator('.product-card')).toHaveCount(12);

    const card = page.locator('.product-card').first();
    const media = card.locator('[data-media]');
    await expect(media).toBeVisible();

    // The shimmer is swapped for the picture: `is-loaded` is set on `load`.
    await expect(media).toHaveClass(/is-loaded/);

    const box = await media.boundingBox();
    expect(box.width / box.height).toBeCloseTo(4 / 3, 1);

    const rendered = await card.locator('img').evaluate((img) => ({
      src: img.currentSrc || img.src,
      complete: img.complete,
      naturalWidth: img.naturalWidth,
    }));
    expect(rendered.complete).toBe(true);
    expect(rendered.naturalWidth).toBeGreaterThan(0);
    expect(rendered.src).toMatch(/\.(jpg|jpeg|png|webp|svg|avif)(\?|$)/i);

    // Native lazy loading is set, so below-the-fold images cost nothing up front.
    await expect(card.locator('img')).toHaveAttribute('loading', 'lazy');
  });

  test('a broken image URL falls back to the placeholder', async ({ page }) => {
    // Serve a product whose image_url points at a file that does not exist.
    await page.route('**/api/v1/products**', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      const applyBroken = (product) => ({ ...product, image_url: '/images/products/does-not-exist.svg' });
      body.items = body.items.map(applyBroken);
      await route.fulfill({ response, json: body });
    });

    await page.goto('/pages/products.html');
    await expect(page.locator('.product-card')).toHaveCount(12);

    const media = page.locator('.product-card').first().locator('[data-media]');
    await expect(media).toHaveClass(/is-(failed|loaded)/);

    const src = await page.locator('.product-card').first().locator('img').evaluate((img) => img.currentSrc || img.src);
    expect(src).toContain('placeholder.svg');

    // The placeholder is visible, not left as an invisible shimmering box.
    await expect(page.locator('.product-card').first().locator('img')).toBeVisible();
  });

  test('a missing image_url still shows the placeholder', async ({ page }) => {
    await page.route('**/api/v1/products**', async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      body.items = body.items.map((product) => ({ ...product, image_url: null }));
      await route.fulfill({ response, json: body });
    });

    await page.goto('/pages/products.html');
    const img = page.locator('.product-card').first().locator('img');
    await expect(img).toHaveAttribute('src', /placeholder\.svg$/);
  });

  test('detail page shows a large image with a stable 1:1 container', async ({ page }) => {
    await page.goto('/pages/product.html?slug=amd-ryzen-7-7800x3d');

    const media = page.locator('.product-detail__media');
    await expect(media).toBeVisible();
    await expect(media).toHaveClass(/is-loaded/);

    const box = await media.boundingBox();
    expect(box.width / box.height).toBeCloseTo(1, 1);

    const rendered = await media.locator('img').evaluate((img) => ({
      complete: img.complete,
      naturalWidth: img.naturalWidth,
    }));
    expect(rendered.complete).toBe(true);
    expect(rendered.naturalWidth).toBeGreaterThan(0);

    // Detail is the LCP image: it must not be lazy.
    await expect(media.locator('img')).not.toHaveAttribute('loading', 'lazy');
  });

  test('every seeded product image resolves to a real file', async ({ page }) => {
    // The API lives on its own origin (see frontend/js/config.js), not behind the static server.
    const slugs = await page.request
      .get('http://localhost:8000/api/v1/products?limit=100')
      .then((res) => res.json());
    expect(slugs.items.length).toBeGreaterThan(0);

    const broken = [];
    for (const product of slugs.items) {
      const head = await page.request.get(product.image_url);
      if (!head.ok() || !(head.headers()['content-type'] || '').startsWith('image/')) {
        broken.push(`${product.image_url} -> ${head.status()} ${head.headers()['content-type']}`);
      }
    }
    expect(broken).toEqual([]);
  });

  test('the placeholder asset itself is reachable', async ({ page }) => {
    // An SVG document has no <body>, so check the served bytes instead.
    const response = await page.request.get('/img/placeholder.svg');
    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('image/svg+xml');
    expect(await response.text()).toContain('No image available');
  });
});

test.describe('Admin image preview', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pages/login.html');
    await page.fill('#identifier', 'admin@example.com');
    await page.fill('#password', 'Admin12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');
    await page.goto('/pages/admin.html#products');
    await expect(page.locator('#admin-product-search')).toBeVisible();
  });

  test('previewing a good URL shows the image', async ({ page }) => {
    await page.click('[data-add]');
    const dialog = page.locator('dialog[open]');
    await expect(dialog).toBeVisible();

    await page.fill('#product-image', '/images/products/cpu/amd-ryzen-7-7800x3d.svg');
    const preview = dialog.locator('[data-image-preview]');
    await expect(preview).toHaveClass(/is-loaded/);
    await expect(preview.locator('[data-image-frame]')).toHaveAttribute('src', /amd-ryzen-7-7800x3d\.svg$/);
    await expect(preview.locator('[data-image-status]')).toContainText('looks good');
  });

  test('previewing a broken URL reports the problem instead of showing nothing', async ({ page }) => {
    await page.click('[data-add]');
    const dialog = page.locator('dialog[open]');

    await page.fill('#product-image', '/images/products/nope.svg');
    const preview = dialog.locator('[data-image-preview]');
    await expect(preview).toHaveClass(/is-failed/);
    await expect(preview.locator('[data-image-status]')).toContainText('could not be loaded');
  });

  test('an unusable URL is rejected before saving', async ({ page }) => {
    await page.click('[data-add]');
    const dialog = page.locator('dialog[open]');

    await page.fill('#product-image', 'javascript:alert(1)');
    await expect(dialog.locator('[data-image-preview]')).toHaveClass(/is-failed/);
    await expect(dialog.locator('[data-image-status]')).toContainText('http');

    // Saving must fail server-side validation, not silently store a bad value.
    await page.fill('#product-name', 'Preview validation product');
    await page.selectOption('#product-category', { index: 1 });
    await page.fill('#product-price', '10.00');
    await page.click('dialog[open] button[type="submit"]');
    await expect(dialog.locator('.field__error')).toContainText('Image URL must be');
  });

  test('an empty URL previews the placeholder', async ({ page }) => {
    await page.click('[data-add]');
    const dialog = page.locator('dialog[open]');
    await expect(dialog.locator('[data-image-preview]')).toHaveClass(/is-loaded/);
    await expect(dialog.locator('[data-image-frame]')).toHaveAttribute('src', /placeholder\.svg$/);
    await expect(dialog.locator('[data-image-status]')).toContainText('placeholder');
  });
});