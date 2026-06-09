import Fastify, { type FastifyInstance } from 'fastify';
import cors from '@fastify/cors';
import { registerReposRoutes } from './routes/repos.js';
import { registerSystemRoutes } from './routes/system.js';

export async function buildServer(): Promise<FastifyInstance> {
  const app = Fastify({ logger: false });

  await app.register(cors, {
    origin: '*',
  });

  app.addHook('onSend', async (_request, reply, payload) => {
    if (!reply.getHeader('Content-Type')) {
      reply.header('Content-Type', 'application/json');
    }
    return payload;
  });

  app.get('/health', async (_request, reply) => {
    reply.header('Content-Type', 'application/json');
    return { status: 'ok' };
  });

  await registerReposRoutes(app);
  await registerSystemRoutes(app);

  return app;
}

async function main(): Promise<void> {
  const host = process.env.FLEX_OBS_HOST ?? '127.0.0.1';
  const portRaw = process.env.FLEX_OBS_PORT ?? '7777';
  const port = Number.parseInt(portRaw, 10);
  if (!Number.isFinite(port) || port <= 0) {
    // eslint-disable-next-line no-console
    console.error(`invalid FLEX_OBS_PORT: ${portRaw}`);
    process.exit(1);
  }

  const app = await buildServer();
  try {
    await app.listen({ host, port });
    // eslint-disable-next-line no-console
    console.log(`flex-observability api listening on http://${host}:${port}`);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(err);
    process.exit(1);
  }
}

// Run main when executed directly (not when imported).
// In ESM with node16 module resolution, import.meta.url comparison handles this.
const invokedDirectly =
  typeof process !== 'undefined' &&
  process.argv[1] &&
  import.meta.url === `file://${process.argv[1]}`;

if (invokedDirectly) {
  void main();
}
