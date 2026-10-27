import { spawn, ChildProcess } from 'node:child_process';
import { createServer, Server } from 'node:http';
import { AddressInfo } from 'node:net';
import { resolve } from 'node:path';
import { test as base, expect } from './fixtures';

type FaultServers = { offlineURL: string; timeoutURL: string };

async function listen(server: Server): Promise<number> {
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  return (server.address() as AddressInfo).port;
}

async function reservePort(): Promise<number> {
  const server = createServer();
  const port = await listen(server);
  await new Promise<void>((resolve) => server.close(() => resolve()));
  return port;
}

export const test = base.extend<object, { faultServers: FaultServers }>({
  faultServers: [
    async ({ playwright }, use) => {
      const processes: ChildProcess[] = [];
      // Deliberately slow HTTP provider: this tests real FastAPI timeout handling,
      // without requiring a GPU or pretending that generated text came from Ollama.
      const slowProvider = createServer((request, response) => {
        request.resume();
        const timer = setTimeout(() => {
          response.writeHead(200, { 'Content-Type': 'application/json' });
          response.end(
            JSON.stringify({
              done: true,
              done_reason: 'stop',
              message: { content: '{"fact_ids":["f1"]}' },
            }),
          );
        }, 5000);
        response.on('close', () => clearTimeout(timer));
      });
      const providerPort = await listen(slowProvider);
      const api = await playwright.request.newContext();
      try {
        async function start(providerPort: number, timeoutSeconds: number): Promise<string> {
          const port = await reservePort();
          const child = spawn(
            process.env['E2E_PYTHON'] ?? 'python',
            ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port)],
            {
              cwd: resolve(__dirname, '../../backend'),
              windowsHide: true,
              stdio: 'ignore', // Do not copy connection details or local paths into CI output.
              env: {
                ...process.env,
                AI_ENABLED: 'true',
                AI_MODEL: 'qwen3:4b',
                AI_BASE_URL: `http://127.0.0.1:${providerPort}/v1`,
                AI_OLLAMA_TRANSPORT: 'native',
                AI_TIMEOUT_SECONDS: String(timeoutSeconds),
              },
            },
          );
          processes.push(child);
          let startupError: Error | undefined;
          child.on('error', (error) => {
            startupError = error;
          });
          const baseURL = `http://127.0.0.1:${port}/api/v1/`;
          await expect
            .poll(
              async () => {
                if (startupError) throw startupError;
                if (child.exitCode !== null)
                  throw new Error('Isolated fault API exited during startup');
                try {
                  return (await api.get(baseURL + 'ready', { timeout: 1000 })).status();
                } catch {
                  return 0;
                }
              },
              { timeout: 30_000 },
            )
            .toBe(200);
          return baseURL;
        }
        // Windows can take around two seconds to report connection refusal.
        // Give that failure time to surface instead of testing the timeout twice.
        const offlineURL = await start(await reservePort(), 5);
        const timeoutURL = await start(providerPort, 1);
        await use({ offlineURL, timeoutURL });
      } finally {
        for (const child of processes) {
          if (child.pid === undefined || child.exitCode !== null || child.signalCode !== null)
            continue;
          const stopped = new Promise<void>((resolve) => child.once('exit', () => resolve()));
          child.kill();
          await stopped;
        }
        slowProvider.closeAllConnections();
        await new Promise<void>((resolve) => slowProvider.close(() => resolve()));
        await api.dispose();
      }
    },
    { scope: 'worker' },
  ],
});

export { expect };
