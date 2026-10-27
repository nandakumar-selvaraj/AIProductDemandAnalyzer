import { test, expect } from './fault-fixtures';

test.describe('isolated provider failures without Ollama', () => {
  test.skip(
    !process.env['E2E_PYTHON'],
    'Set E2E_PYTHON to a backend interpreter to run isolated fault APIs',
  );

  for (const fault of ['offline', 'timeout'] as const) {
    test(`${fault}: actual backend error remains recoverable in the browser`, async ({
      page,
      openPage,
      faultServers,
    }) => {
      const status = fault === 'offline' ? 503 : 504;
      const backend = fault === 'offline' ? faultServers.offlineURL : faultServers.timeoutURL;
      // Forward the browser's POST to an actual isolated FastAPI instance.
      // Preserve the backend HTTP response; do not manufacture a browser response.
      await page.route('**/api/v1/assistant/chat', async (route) => {
        const response = await route.fetch({ url: backend + 'assistant/chat' });
        await route.fulfill({ response });
      });
      await openPage('ai-assistant');
      await page
        .getByRole('textbox', { name: 'Your business question', exact: true })
        .fill('How does this application calculate forecasts?');
      const response = page.waitForResponse((r) => r.url().endsWith('/assistant/chat'));
      await page.getByRole('button', { name: 'Send', exact: true }).click();
      if (fault === 'timeout') {
        await expect(
          page.getByRole('button', { name: 'Cancel request', exact: true }),
        ).toBeVisible();
        await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled();
      }
      expect((await response).status()).toBe(status);
      await expect(page.getByRole('alert')).toContainText(
        fault === 'offline' ? 'could not be reached' : 'timed out',
      );
      await expect(page.getByRole('button', { name: 'Retry answer', exact: true })).toBeVisible();
      await expect(page.getByLabel('Assistant answer', { exact: true })).toHaveCount(0);
      await expect(
        page.getByRole('textbox', { name: 'Your business question', exact: true }),
      ).toBeEnabled();
    });
  }
});
