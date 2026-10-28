import { test, expect, Page } from '@playwright/test';

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
