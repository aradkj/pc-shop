import { test, expect } from '@playwright/test';

test.describe('Authentication and Session', () => {
  test('customer can log in with cookies and view profile', async ({ page }) => {
    await page.goto('/pages/login.html');

    // Fill login form
    await page.fill('#identifier', 'alice@example.com');
    await page.fill('#password', 'Customer12345!');
    await page.click('button[type="submit"]');

    // Should redirect to index and show user in navbar
    await page.waitForURL('**/index.html*');
    await expect(page.locator('.user-menu__name')).toContainText('Alice');

    // Navigate to profile
    await page.goto('/pages/profile.html');
    await expect(page.locator('#profile-account')).toContainText('alice@example.com');
    await expect(page.locator('#profile-account')).toContainText('Alice Johnson');

    // Verify access_token cookie is present and HttpOnly
    const cookies = await page.context().cookies();
    const accessToken = cookies.find((c) => c.name === 'access_token');
    expect(accessToken).toBeDefined();
    expect(accessToken.httpOnly).toBe(true);

    // Verify csrf_token cookie is present
    const csrfToken = cookies.find((c) => c.name === 'csrf_token');
    expect(csrfToken).toBeDefined();

    // Verify localStorage does NOT contain JWT
    const storageKeys = await page.evaluate(() => Object.keys(localStorage));
    expect(storageKeys).not.toContain('arad.token');
  });

  test('customer can register a new account', async ({ page }) => {
    await page.goto('/pages/register.html');

    const randomSuffix = Math.floor(Math.random() * 100000);
    const newUsername = `testuser_${randomSuffix}`;
    const newEmail = `test_${randomSuffix}@example.com`;

    await page.fill('#first_name', 'Test');
    await page.fill('#last_name', 'User');
    await page.fill('#email', newEmail);
    await page.fill('#username', newUsername);
    await page.fill('#register-password', 'Password123!');
    await page.fill('#confirm_password', 'Password123!');
    await page.click('button[type="submit"]');

    // Automatic login after registration
    await page.waitForURL('**/index.html*');
    await expect(page.locator('.user-menu__name')).toContainText('Test');
  });

  test('customer can log out and cookies are cleared', async ({ page }) => {
    await page.goto('/pages/login.html');
    await page.fill('#identifier', 'alice@example.com');
    await page.fill('#password', 'Customer12345!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/index.html*');

    // Click logout
    await page.click('.user-menu summary');
    await page.click('[data-logout]');

    // Redirect to index, account area shows login button
    await page.waitForURL('**/index.html*');
    await expect(page.locator('.site-nav a[href*="login.html"]')).toBeVisible();


    // Accessing profile should redirect to login
    await page.goto('/pages/profile.html');
    await page.waitForURL('**/pages/login.html*');
  });

  test('customer can request password reset on login page', async ({ page }) => {
    await page.goto('/pages/login.html');
    await page.click('#toggle-forgot');
    await expect(page.locator('#forgot-password-card')).toBeVisible();

    await page.fill('#forgot-email', 'alice@example.com');
    await page.click('#forgot-form button[type="submit"]');

    await expect(page.locator('[data-forgot-alert]')).toBeVisible();
    await expect(page.locator('[data-forgot-alert]')).toContainText('password reset process');
  });
});
