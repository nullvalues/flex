import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../src/server.js';
import {
  createFixtureProject,
  cleanupFixtureProject,
  writeRegistry,
  type FixtureProject,
} from './fixtures/project.js';

describe('GET /api/repos/:id/lessons', () => {
  let app: FastifyInstance;
  let project: FixtureProject;
  const originalRegistry = process.env.FLEX_OBS_REGISTRY;

  beforeAll(async () => {
    project = await createFixtureProject();
    const registryPath = await writeRegistry(project.dir, [
      { id: 'demo-a', project_dir: project.dir, color: '#ff0000' },
    ]);
    process.env.FLEX_OBS_REGISTRY = registryPath;
    app = await buildServer('127.0.0.1');
  });

  afterAll(async () => {
    await app.close();
    await cleanupFixtureProject(project);
    if (originalRegistry === undefined) delete process.env.FLEX_OBS_REGISTRY;
    else process.env.FLEX_OBS_REGISTRY = originalRegistry;
  });

  it('returns 200 with parsed lessons, promotion filter applied, against fixture data', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/repos/demo-a/lessons' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { repo_id: string; generated_at: string; lessons: unknown[] };
    expect(body.repo_id).toBe('demo-a');
    expect(typeof body.generated_at).toBe('string');
    expect(body.lessons).toHaveLength(2);

    const byId = Object.fromEntries(
      (body.lessons as Array<Record<string, unknown>>).map((l) => [l.id, l]),
    );
    // lesson-001: applied + module-named affects + procedural-verb description
    // -> a real promotion candidate.
    expect(byId['lesson-001']).toMatchObject({
      status: 'applied',
      promotion_candidate: true,
    });
    expect((byId['lesson-001'].promotion_reasons as string[]).length).toBeGreaterThan(0);

    // lesson-002: status 'draft' -> never a promotion candidate.
    expect(byId['lesson-002']).toMatchObject({
      status: 'draft',
      promotion_candidate: false,
      promotion_reasons: [],
    });
  });

  it('failure-shaped: an unregistered repo id returns 404, not a crash', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/repos/does-not-exist/lessons' });
    expect(res.statusCode).toBe(404);
    expect(res.json()).toEqual({ error: 'repo not found', id: 'does-not-exist' });
  });
});
