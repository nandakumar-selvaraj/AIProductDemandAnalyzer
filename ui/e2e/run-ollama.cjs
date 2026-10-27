// Explicit, cross-platform opt-in; plain `playwright test` never invokes Ollama.
const { spawnSync } = require('node:child_process');
const result = spawnSync(
  process.execPath,
  [require.resolve('@playwright/test/cli'), 'test', '--grep', '@ollama', ...process.argv.slice(2)],
  { env: { ...process.env, E2E_OLLAMA: '1' }, stdio: 'inherit', windowsHide: true },
);
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
