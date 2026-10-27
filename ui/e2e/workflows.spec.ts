import { readFile } from 'node:fs/promises';
import { test, expect, selectProduct } from './fixtures';

test('dashboard renders the connected database summary', async ({ page, api, openPage }) => {
  const response = await api.get('dashboard/summary');
  expect(response.ok()).toBeTruthy();
  const summary = await response.json();
  await openPage('dashboard');
  await expect(page.locator('body')).toContainText(
    summary.total_units_sold.toLocaleString('en-US'),
  );
});

test('products search and pagination agree with the API', async ({
  page,
  api,
  scope,
  openPage,
}) => {
  const response = await api.get(
    `products?search=${encodeURIComponent(scope.productCode)}&page_size=10`,
  );
  expect(response.ok()).toBeTruthy();
  const expected = await response.json();
  await openPage('products');
  await page
    .getByRole('searchbox', { name: 'Search products', exact: true })
    .fill(scope.productCode);
  const searched = page.waitForResponse(
    (r) => r.url().includes('/products?') && r.url().includes('search='),
  );
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  expect((await searched).ok()).toBeTruthy();
  await expect(page.locator('tbody tr')).toHaveCount(expected.items.length);
  for (const product of expected.items)
    await expect(page.locator('tbody')).toContainText(product.item_code);
  await expect(page.getByRole('button', { name: 'Previous', exact: true })).toBeDisabled();
  if (expected.total_pages > 1) {
    await page.getByRole('button', { name: 'Next', exact: true }).click();
    await expect(page.getByRole('status')).toContainText('Page 2');
  } else {
    await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeDisabled();
  }
});

test('demand analysis renders actual sales and observation rows', async ({
  page,
  scope,
  openPage,
}) => {
  await openPage('demand-analysis');
  await selectProduct(page, scope);
  const response = page.waitForResponse((r) =>
    r.url().includes(`/products/${scope.productId}/analytics`),
  );
  await page.getByRole('button', { name: 'Apply Filters', exact: true }).click();
  const result = await response;
  expect(result.ok()).toBeTruthy();
  const data = await result.json();
  expect(data.daily_sales.length).toBeGreaterThan(0);
  await expect(page.getByLabel('Historical sales summary')).toContainText(
    data.total_units_sold.toLocaleString('en-US'),
  );
  await expect(page.locator('.observations tbody tr').first()).toBeVisible();
});

test('completed forecast predictions and evaluation load', async ({
  page,
  api,
  scope,
  openPage,
}) => {
  const response = await api.get(`forecasts/${scope.runId}/predictions`);
  expect(response.ok()).toBeTruthy();
  const predictions = await response.json();
  await openPage('forecasts');
  await page.getByRole('button', { name: 'View latest run details', exact: true }).click();
  const table = page.locator('app-forecast-predictions');
  await expect(table.locator('tbody tr')).toHaveCount(predictions.items.length);
  await expect(table).toContainText(`${predictions.total_records} predictions`);
  const first = table.locator('tbody tr').first();
  await expect(first).toContainText(predictions.items[0].forecast_date);
  await expect(first).toContainText(
    Number(predictions.items[0].predicted_units).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  );
  const evaluation = page.waitForResponse((r) => r.url().endsWith('/forecasts/evaluate'));
  await page.getByRole('button', { name: 'Evaluate run', exact: true }).click();
  expect((await evaluation).ok()).toBeTruthy();
  await expect(page.locator('app-accuracy-metrics')).toBeVisible();
});

test('reports export every returned daily observation', async ({
  page,
  scope,
  openPage,
}, testInfo) => {
  await openPage('reports');
  await selectProduct(page, scope);
  const response = page.waitForResponse((r) =>
    r.url().includes(`/products/${scope.productId}/analytics`),
  );
  await page.getByRole('button', { name: 'Generate Report', exact: true }).click();
  const result = await response;
  expect(result.ok()).toBeTruthy();
  const data = await result.json();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export Daily CSV', exact: true }).click();
  const file = await download;
  const target = testInfo.outputPath('historical-sales.csv');
  await file.saveAs(target);
  const csv = (await readFile(target, 'utf8')).replace(/^\uFEFF/, '').trim();
  // Quoted CSV cells can contain commas; compare each observation's final two cells.
  const lines = csv.split(/\r?\n/);
  expect(lines).toHaveLength(data.daily_sales.length + 1);
  expect(lines[0]).toContain('"period","units_sold"');
  data.daily_sales.forEach((row: { period: string; units_sold: number }, index: number) => {
    expect(lines[index + 1].endsWith(`,"${row.period}","${row.units_sold}"`)).toBe(true);
  });
});

test('disabled assistant displays a recoverable backend error', async ({ page, openPage }) => {
  test.skip(
    process.env['E2E_AI_DISABLED'] !== '1',
    'Only run against an explicitly AI-disabled backend',
  );
  await openPage('ai-assistant');
  await page
    .getByRole('textbox', { name: 'Your business question', exact: true })
    .fill('How are forecasts calculated?');
  const response = page.waitForResponse((r) => r.url().endsWith('/assistant/chat'));
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  expect((await response).status()).toBe(503);
  await expect(page.getByRole('alert')).toContainText('disabled');
  await expect(page.getByRole('button', { name: 'Retry answer', exact: true })).toBeVisible();
  await expect(page.getByLabel('Assistant answer', { exact: true })).toHaveCount(0);
});
