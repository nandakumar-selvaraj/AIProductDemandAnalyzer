import { test, expect } from '@playwright/test';

test.describe('production synthetic public demo', () => {
  test.skip(process.env['E2E_PUBLIC_DEMO'] !== '1', 'Requires the disposable production Docker stack');

  test('labels the synthetic dataset and shows read-only sales and forecasts', async ({ page }) => {
    await page.goto('/demo');
    await expect(page.getByRole('status').filter({ hasText: 'Historical synthetic demo data' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Demand Overview', exact: true })).toBeVisible();
    await page.goto('/demo/forecasts');
    await expect(page.getByRole('heading', { name: 'Forecasts', exact: true })).toBeVisible();
    await expect(page.getByText('Read-only demonstration.', { exact: false })).toBeVisible();
    await expect(page.locator('app-create-forecast')).toHaveCount(0);
    await expect(page.locator('app-backtesting')).toHaveCount(0);
    await expect(page.getByText('No completed forecast run is available.', { exact: false })).toHaveCount(0);
  });

  test('rejects anonymous mutations and unrestricted chat through the proxy', async ({ request }) => {
    for (const path of ['/ingestion/sales', '/forecasts', '/forecasts/backtest', '/assistant/chat']) {
      const response = await request.post(`/api/v1${path}`, { data: {} });
      expect(response.status()).toBe(401);
    }
    const products = await request.get('/api/v1/products');
    expect(products.status()).toBe(200);
    expect((await products.json()).total_records).toBe(2);
  });

  test('AI stays disabled without asking for credentials or exposing a text composer', async ({ page }) => {
    await page.goto('/demo/ai-assistant');
    await expect(page.getByRole('heading', { name: 'AI Business Assistant' })).toBeVisible();
    await expect(page.getByText('Demo AI is currently disabled.', { exact: false })).toBeVisible();
    await expect(page.locator('textarea')).toHaveCount(0);
    await expect(page.getByRole('button', { name: /send/i })).toHaveCount(0);
  });
});
