import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../src/server.js';
import {
  createFixtureProject,
  cleanupFixtureProject,
  writeRegistry,
  type FixtureProject,
} from './fixtures/project.js';

describe('GET /api/repos/:id/system', () => {
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

  it('returns 200 with the parsed phase/story tree for a registered repo', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/repos/demo-a/system' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as {
      repo_id: string;
      generated_at: string;
      phases: Array<Record<string, unknown>>;
      resolver_state: unknown;
    };
    expect(body.repo_id).toBe('demo-a');
    expect(typeof body.generated_at).toBe('string');
    expect(Array.isArray(body.phases)).toBe(true);
    expect(body.phases).toHaveLength(1);

    const phase1 = body.phases[0] as Record<string, unknown>;
    expect(phase1.phase_ref).toBe('1');
    expect(phase1.file).toBe('docs/phases/phase-1.md');
    expect(phase1.status).toBe('complete');
    expect(phase1.era).toBe('001');
    expect(phase1.deferred).toEqual(['DEMO-002']);

    const stories = phase1.stories as Array<Record<string, unknown>>;
    expect(stories).toHaveLength(1);
    expect(stories[0]).toMatchObject({
      id: 'DEMO-001',
      rail: 'DEMO',
      title: 'Demo fixture story',
      status: 'complete',
      story_class: 'code',
      flex_factor: 1.0,
    });

    // readResolverState shells out to `flex_build.py resolver-state`. It
    // returns null here — not because the fixture is invalid (it's a real,
    // valid flex-shaped tree), but because of a real, pre-existing path bug
    // in getFlexBuildPath() (an extra '..' hop misses the `skills/` segment,
    // so the spawned command always ENOENTs) — filed as CER-142, out of this
    // story's declared `touches:` scope. null is the actual shipped
    // behaviour today; this assertion pins it so a future fix (CER-142) is
    // visible here as a test update, not a silent behaviour change.
    expect(body.resolver_state).toBeNull();
  });

  it('failure-shaped: an unregistered repo id returns 404, not a crash', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/repos/does-not-exist/system' });
    expect(res.statusCode).toBe(404);
    expect(res.json()).toEqual({ error: 'repo not found', id: 'does-not-exist' });
  });
});
