import { test as base, expect, APIRequestContext, Page } from '@playwright/test';
import { AssistantResponse } from '../src/app/core/models/assistant.models';

export type Scope = { runId: number; productId: number; storeId: number; productCode: string };
type Fixtures = {
  api: APIRequestContext;
  scope: Scope;
  openPage: (route: string) => Promise<void>;
};

export const test = base.extend<Fixtures>({
  api: async ({ playwright }, use) => {
    const api = await playwright.request.newContext({
      baseURL: process.env['E2E_API_URL'] ?? 'http://127.0.0.1:8000/api/v1/',
      timeout: 150_000,
    });
    try {
      const ready = await api.get('ready');
      expect(ready.status(), 'FastAPI must have a migrated, connected PostgreSQL database').toBe(
        200,
      );
      await use(api);
    } finally {
      await api.dispose();
    }
  },
  scope: async ({ api }, use) => {
    const latest = await api.get('forecasts/latest');
    expect(latest.ok()).toBeTruthy();
    const run = await latest.json();
    expect(
      run,
      'Seed the isolated E2E database or supply an existing completed run',
    ).not.toBeNull();
    const predictions = await api.get(`forecasts/${run.id}/predictions?page_size=1`);
    expect(predictions.ok()).toBeTruthy();
    const first = (await predictions.json()).items[0];
    expect(first, 'Completed run needs at least one saved prediction').toBeTruthy();
    const products = await api.get('products?page_size=500');
    expect(products.ok()).toBeTruthy();
    const product = (await products.json()).items.find(
      (row: { id: number }) => row.id === first.product_id,
    );
    expect(product, 'The sampled prediction must refer to an existing product').toBeTruthy();
    await use({
      runId: run.id,
      productId: first.product_id,
      storeId: first.store_id,
      productCode: product.item_code,
    });
  },
  openPage: async ({ page }, use) => {
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await use(async (route) => {
      await page.goto(`/${route}`);
      await expect(page.locator('h1')).toBeVisible();
    });
    expect(errors, 'Uncaught browser exceptions').toEqual([]);
  },
});

export { expect };

export async function selectProduct(page: Page, scope: Scope) {
  const picker = page.locator('app-catalog-picker[kind="products"]');
  await picker.getByRole('searchbox').fill(scope.productCode);
  const response = page.waitForResponse(
    (r) => r.url().includes('/products?') && r.url().includes('search='),
  );
  await picker.getByRole('button', { name: 'Search products', exact: true }).click();
  expect((await response).ok()).toBeTruthy();
  await expect(picker.locator('select')).toBeEnabled();
  // Angular serializes ngValue as an index/value pair, so resolve by visible item code.
  const option = picker
    .locator('option')
    .filter({ hasText: `· ${scope.productCode}` })
    .first();
  const value = await option.getAttribute('value');
  expect(value).not.toBeNull();
  await picker.locator('select').selectOption(value!);
}

export async function ask(page: Page, message: string): Promise<AssistantResponse> {
  const answers = page.getByLabel('Assistant answer', { exact: true });
  const count = await answers.count();
  await page.getByRole('textbox', { name: 'Your business question', exact: true }).fill(message);
  const response = page.waitForResponse((r) => r.url().endsWith('/assistant/chat'), {
    timeout: 150_000,
  });
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  const result = await response;
  expect(result.status()).toBe(200);
  const data: AssistantResponse = await result.json();
  expect(data.answer.trim()).not.toBe('');
  expect(data.provider_used, 'This opt-in suite must exercise real inference').toBe(true);
  await expect(answers).toHaveCount(count + 1);
  await expect(answers.last()).toContainText(data.answer.split('\n')[0]);
  return data;
}
