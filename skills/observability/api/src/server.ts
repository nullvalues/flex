import Fastify, { type FastifyInstance } from 'fastify';
import cors from '@fastify/cors';
import fastifyStatic from '@fastify/static';
import * as path from 'node:path';
import * as fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { registerReposRoutes } from './routes/repos.js';
import { registerSystemRoutes } from './routes/system.js';
import { registerLessonsRoutes } from './routes/lessons.js';
import { registerUserRoutes } from './routes/user.js';
import { registerContextRoutes } from './routes/context.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Resolve the UI's built dist/ directory.
 * In dev (NODE_ENV !== 'production') the Vite dev server handles `/`, so this
 * path is not used. In production it points at `skills/observability/ui/dist`.
 * `dirname(import.meta.url)` for this module resolves to
 * `skills/observability/api/dist/` after build (or `api/src/` under tsx),
 * so we go up two levels and into `ui/dist`.
 */
function resolveUiDistDir(): string {
  // From either api/dist/ or api/src/, the UI dist is at ../ui/dist.
  // Resolve relative to this module's directory; tolerate both layouts.
  const candidate = path.resolve(__dirname, '..', '..', 'ui', 'dist');
  return candidate;
}

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
  await registerLessonsRoutes(app);
  await registerUserRoutes(app);
  await registerContextRoutes(app);

  // Static UI serving — production only. The Vite dev server handles /
  // during development. In production the Fastify server serves the
  // built SPA from skills/observability/ui/dist (INFRA-161 §12).
  if (process.env.NODE_ENV === 'production') {
    const uiDist = resolveUiDistDir();
    if (fs.existsSync(uiDist)) {
      await app.register(fastifyStatic, {
        root: uiDist,
        prefix: '/',
        index: ['index.html'],
        decorateReply: false,
      });
      // SPA fallback: any non-/api, non-/health GET that didn't match a
      // static file returns index.html so client routes work on reload.
      app.setNotFoundHandler((request, reply) => {
        if (request.method !== 'GET') {
          reply.code(404);
          return { error: 'not found' };
        }
        if (request.url.startsWith('/api') || request.url.startsWith('/health')) {
          reply.code(404);
          return { error: 'not found' };
        }
        return reply.sendFile('index.html');
      });
    }
  }

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
