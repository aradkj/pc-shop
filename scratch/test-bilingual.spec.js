import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const screenshotDir = path.resolve('scratch', 'screenshots', 'bilingual');
if (!fs.existsSync(screenshotDir)) {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

test.describe('Bilingual Language Selector & Popup Tests', () => {
  test('user can open popup modal and switch language between English and Persian', async ({ page }) => {
    // 1. Visit homepage
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    // Default language is English
    expect(await page.locator('html').getAttribute('lang')).toBe('en');
    expect(await page.locator('html').getAttribute('dir')).toBe('ltr');

    // Check language button is present in the header
    const langBtn = page.locator('#lang-picker-btn');
    await expect(langBtn).toBeVisible();
    await expect(langBtn).toContainText('EN');

    // 2. Click the language button to open pop-up modal
    await langBtn.click();

    // Check dialog/modal opens
    const modal = page.locator('dialog.modal');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('Language Settings');

    // Take screenshot of open language selection modal
    await page.screenshot({ path: path.join(screenshotDir, '1-language-modal-open.png') });

    // Verify both English and Persian options exist
    const enOption = modal.locator('[data-choose-lang="en"]');
    const faOption = modal.locator('[data-choose-lang="fa"]');
    await expect(enOption).toBeVisible();
    await expect(faOption).toBeVisible();

    // 3. Select Persian (فارسی)
    await faOption.click();

    // Wait for reload and page load
    await page.waitForLoadState('networkidle');

    // Verify document attributes changed to Persian RTL
    expect(await page.locator('html').getAttribute('lang')).toBe('fa');
    expect(await page.locator('html').getAttribute('dir')).toBe('rtl');

    // Verify header button badge updated to Persian
    await expect(page.locator('#lang-picker-btn')).toContainText('فارسی');

    // Verify translated elements
    await expect(page.locator('.site-nav')).toContainText('خانه');
    await expect(page.locator('.site-nav')).toContainText('فروشگاه');

    // Take screenshot of Persian RTL homepage
    await page.screenshot({ path: path.join(screenshotDir, '2-persian-homepage-rtl.png') });

    // 4. Click language button again in Persian mode
    await page.locator('#lang-picker-btn').click();
    const modalFa = page.locator('dialog.modal');
    await expect(modalFa).toBeVisible();
    await expect(modalFa).toContainText('انتخاب زبان سایت');

    // Take screenshot of modal in Persian
    await page.screenshot({ path: path.join(screenshotDir, '3-language-modal-persian.png') });

    // Switch back to English
    await modalFa.locator('[data-choose-lang="en"]').click();
    await page.waitForLoadState('networkidle');

    // Verify back to English
    expect(await page.locator('html').getAttribute('lang')).toBe('en');
    expect(await page.locator('html').getAttribute('dir')).toBe('ltr');
    await expect(page.locator('#lang-picker-btn')).toContainText('EN');
  });
});
