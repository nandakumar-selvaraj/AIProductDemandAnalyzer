// Test-only TCP forwarding preserves the exact localhost TLS authority and Origin.
// The browser and proxy communicate entirely inside the disposable Docker network.
const net = require('node:net');
const { spawn } = require('node:child_process');

const forwarder = net.createServer((client) => {
  const upstream = net.connect(443, 'proxy');
  client.pipe(upstream).pipe(client);
  client.on('error', () => upstream.destroy());
  upstream.on('error', () => client.destroy());
});

async function run(file) {
  const status = await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['node_modules/@playwright/test/cli.js', 'test', file], {
      stdio: 'inherit', env: process.env,
    });
    child.on('error', reject);
    child.on('exit', resolve);
  });
  if (status !== 0) throw new Error(`Browser validation failed: ${file}`);
}

async function main() {
  const port = Number(new URL(process.env.E2E_BASE_URL).port);
  await new Promise((resolve) => forwarder.listen(port, '127.0.0.1', resolve));
  try {
    await run('public-demo.spec.ts');
    await run('authentication.spec.ts');
  } finally {
    forwarder.close();
  }
}

main().then(() => process.exit(0)).catch(() => {
  console.error('Isolated Linux production browser validation failed; credential details omitted');
  process.exit(1);
});
