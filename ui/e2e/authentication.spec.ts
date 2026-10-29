import { test, expect, Page } from '@playwright/test';

// Auth traces/video can record password input and Authorization headers.
test.use({ screenshot: 'off', trace: 'off', video: 'off' });

test.describe('JWT browser sessions', () => {
  test.skip(process.env['E2E_AUTH'] !== '1', 'Requires isolated synthetic JWT users');

  async function login(page: Page, role: 'admin' | 'viewer') {
    const email = process.env[role === 'admin' ? 'E2E_ADMIN_EMAIL' : 'E2E_VIEWER_EMAIL'];
    const password = process.env['E2E_AUTH_PASSWORD'];
    expect(email).toBeTruthy(); expect(password).toBeTruthy();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login$/);
    await page.getByLabel('Email', { exact: true }).fill(email!);
    await page.getByLabel('Password', { exact: true }).fill(password!);
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Demand Overview', exact: true })).toBeVisible();
  }

  test('admin login, dashboard and browser refresh preserve the valid session', async ({ page }) => {
    await login(page, 'admin');
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Demand Overview', exact: true })).toBeVisible();
    await page.goto('/forecasts');
    await expect(page.locator('app-create-forecast')).toBeVisible();
    const stored = await page.evaluate(() => [localStorage.length, sessionStorage.length]);
    expect(stored).toEqual([0, 0]);
  });

  test('viewer login permits reports/analytical POSTs and rejects uploads', async ({ page, baseURL }) => {
    await login(page, 'viewer');
    await expect(page.getByRole('link', { name: 'Data Management', exact: true })).toHaveCount(0);
    await page.goto('/data-management');
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.goto('/forecasts');
    await expect(page.getByRole('heading', { name: 'Forecasts', exact: true })).toBeVisible();
    await expect(page.locator('app-create-forecast')).toHaveCount(0);
    await expect(page.locator('app-backtesting')).toBeVisible();
    const me = await page.request.get('/api/v1/auth/me');
    const session = await me.json();
    const headers = { Origin: new URL(baseURL!).origin, 'X-CSRF-Token': session.csrf_token };
    const upload = await page.request.post('/api/v1/ingestion/sales', { headers, data: {} });
    expect(upload.status()).toBe(403);
    const forecast = await page.request.post('/api/v1/forecasts', { headers, data: {} });
    expect(forecast.status()).toBe(403);
    const latest = await (await page.request.get('/api/v1/forecasts/latest')).json();
    const evaluation = await page.request.post('/api/v1/forecasts/evaluate', {
      headers, data: { forecast_run_id: latest.id },
    });
    expect(evaluation.status()).toBe(200);
  });

  test('admin uploads synthetic historical CSV and repeat upload updates existing totals', async ({ page }) => {
    await login(page, 'admin');
    await page.getByRole('link', { name: 'Data Management', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Data Management', exact: true })).toBeVisible();
    const csv = { name: 'synthetic-kaggle.csv', mimeType: 'text/csv',
      buffer: Buffer.from('date,store,item,sales\n2013-01-01,1,1,10\n2013-01-01,1,1,12\n') };
    await expect(page.getByLabel('Sales CSV file')).toBeEnabled();
    await page.getByLabel('Sales CSV file').setInputFiles(csv);
    await page.getByRole('button', { name: 'Upload CSV', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Upload completed' })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Latest upload result' })).toContainText('Duplicate rows skipped1');
    await page.getByLabel('Sales CSV file').setInputFiles(csv);
    const response = page.waitForResponse((r) => r.url().endsWith('/ingestion/sales') && r.request().method() === 'POST');
    await page.getByRole('button', { name: 'Upload CSV', exact: true }).click();
    const result = await (await response).json();
    expect(result.updated).toBe(1); expect(result.inserted).toBe(0);
    await expect(page.getByRole('heading', { name: 'Upload completed' })).toBeVisible();
  });

  test('admin session expiry removes the upload page', async ({ page }) => {
    await page.clock.install();
    await login(page, 'admin');
    await page.goto('/data-management');
    await expect(page.getByRole('heading', { name: 'Data Management', exact: true })).toBeVisible();
    await page.clock.fastForward(31 * 60 * 1000);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.locator('input[type="file"]')).toHaveCount(0);
  });

  test('restricted Swagger authorizes a CLI API token without browser cookies', async ({ page }) => {
    test.skip(process.env['E2E_PUBLIC_DEMO'] === '1', 'Production Swagger remains disabled');
    const token = process.env['E2E_API_TOKEN'];
    expect(Boolean(token)).toBe(true);
    const api = process.env['E2E_API_URL']!;
    try {
    await page.goto(new URL('/docs', api).href);
    await page.getByRole('button', { name: 'Authorize', exact: true }).first().click();
    // Playwright fill() step titles can contain their value in HTML reports.
    await page.locator('input[aria-label="auth-bearer-value"]').evaluate((input, value) => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
      setter.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
    }, token!);
    await page.getByRole('button', { name: 'Apply credentials', exact: true }).first().click({ timeout: 15000 });
    await page.getByRole('button', { name: 'Close', exact: true }).first().click();
    // Execute the actual Swagger request using its in-memory authorization state.
    await page.locator('#operations-Products-list_products_api_v1_products_get').click();
    await page.getByRole('button', { name: 'Try it out', exact: true }).click();
    const response = page.waitForResponse((r) => r.url().includes('/api/v1/products?') && r.request().method() === 'GET');
    await page.getByRole('button', { name: 'Execute', exact: true }).click();
    expect((await response).status()).toBe(200);
    expect(await page.context().cookies()).toHaveLength(0);
    } catch {
      throw new Error('Restricted Swagger authorization validation failed; credential details omitted');
    } finally {
      // Clear Swagger state before Playwright captures any failure context.
      await page.goto('about:blank');
    }
  });

  test('expiration timer removes the protected page and redirects to login', async ({ page }) => {
    await page.clock.install();
    await login(page, 'viewer');
    await page.clock.fastForward(31 * 60 * 1000);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
    await expect(page.locator('.content-area')).toHaveCount(0);
  });

  test('logout revokes the old cookie and browser Back cannot restore protected content', async ({ page }) => {
    await login(page, 'viewer');
    const cookie = (await page.context().cookies()).find((c) => c.name.endsWith('demand_session'));
    expect(cookie?.httpOnly).toBe(true);
    await page.goto('/products');
    await expect(page.getByRole('heading', { name: /^Products/ })).toBeVisible();
    await page.getByRole('button', { name: 'Log out', exact: true }).click();
    await expect(page).toHaveURL(/\/login$/);
    const response = await page.request.get('/api/v1/products', {
      headers: { Cookie: `${cookie!.name}=${cookie!.value}` },
    });
    expect(response.status()).toBe(401);
    await page.goBack();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('heading', { name: /^Products/ })).toHaveCount(0);
  });
});
