import { test, expect, ask } from './fixtures';

test.describe('real local inference @ollama', () => {
  test.beforeEach(async ({ api, openPage }) => {
    const ready = await api.get('assistant/ready');
    expect(ready.status(), 'Opt-in requires enabled Ollama and the configured model').toBe(200);
    await openPage('ai-assistant');
  });

  test('general answer includes application sources', async ({ page }) => {
    const data = await ask(page, 'How does this application calculate forecasts?');
    expect(data.intent).toBe('general');
    expect(data.sources.some((source) => source.type === 'application')).toBe(true);
    await page.getByLabel('Assistant answer', { exact: true }).locator('summary').click();
    await expect(page.getByLabel('Assistant answer', { exact: true })).toContainText('application');
  });

  test('forecast evidence, follow-up and New Chat retain correct ownership and scope', async ({
    page,
    api,
    scope,
  }) => {
    const forecast = await ask(
      page,
      `What is the forecast for product ${scope.productId} and store ${scope.storeId}?`,
    );
    expect(forecast.context.forecast_run_id).toBe(scope.runId);
    expect(forecast.context.product_id).toBe(scope.productId);
    expect(forecast.context.store_id).toBe(scope.storeId);
    expect(
      forecast.sources.some(
        (source) =>
          source.forecast_run_id === scope.runId &&
          source.product_id === scope.productId &&
          source.store_id === scope.storeId,
      ),
    ).toBe(true);
    const response = await api.get(`forecasts/${scope.runId}/predictions?page_size=500`);
    expect(response.ok()).toBeTruthy();
    const first = await response.json();
    const rows = [...first.items];
    for (let index = 2; index <= first.total_pages; index++) {
      const next = await api.get(
        `forecasts/${scope.runId}/predictions?page_size=500&page=${index}`,
      );
      expect(next.ok()).toBeTruthy();
      rows.push(...(await next.json()).items);
    }
    // Numeric(12,3) values are summed as integer milli-units to avoid floating-point drift.
    const scoped = rows.filter(
      (row) => row.product_id === scope.productId && row.store_id === scope.storeId,
    );
    const milli = scoped.reduce(
      (sum, row) => sum + Math.round(Number(row.predicted_units) * 1000),
      0,
    );
    expect(forecast.answer).toContain((milli / 1000).toFixed(3));
    await page.getByLabel('Assistant answer', { exact: true }).locator('summary').click();
    await expect(page.getByLabel('Assistant answer', { exact: true })).toContainText(
      `Product #${scope.productId}`,
    );

    const followUp = await ask(page, 'How reliable is this forecast?');
    expect(followUp.conversation_id).toBe(forecast.conversation_id);
    expect(followUp.context.product_id).toBe(scope.productId);
    expect(followUp.intent).toBe('evaluation');
    await page.getByRole('button', { name: 'New Chat', exact: true }).click();
    await expect(page.getByLabel('Assistant answer', { exact: true })).toHaveCount(0);
    await expect(page.locator('#assistant-product')).toHaveValue('');
    await expect(page.locator('#assistant-store')).toHaveValue('');
    const fresh = await ask(page, 'How does this application calculate forecasts?');
    expect(fresh.conversation_id).not.toBe(forecast.conversation_id);
    expect(fresh.context.product_id).toBeNull();
    expect(fresh.context.forecast_run_id).toBeNull();
  });

  test('missing history returns a limitation without inference', async ({ page, scope }) => {
    await page.locator('#assistant-product').fill(String(scope.productId));
    await page.locator('#assistant-start').fill('2099-01-01');
    await page.locator('#assistant-end').fill('2099-01-02');
    await page
      .getByRole('textbox', { name: 'Your business question', exact: true })
      .fill('How many units did this product sell?');
    const response = page.waitForResponse((r) => r.url().endsWith('/assistant/chat'));
    await page.getByRole('button', { name: 'Send', exact: true }).click();
    const result = await response;
    expect(result.status()).toBe(200);
    const data = await result.json();
    expect(data.provider_used).toBe(false);
    expect(data.sources).toEqual([]);
    expect(data.answer).toContain('No recorded sales observations');
    await expect(page.getByLabel('Assistant answer', { exact: true })).toContainText(
      'Missing sales are not zero',
    );
  });
});
