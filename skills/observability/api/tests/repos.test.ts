import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import * as path from 'node:path';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../src/server.js';
import {
  createFixtureProject,
  cleanupFixtureProject,
  writeRegistry,
  type FixtureProject,
} from './fixtures/project.js';

describe('GET /api/repos', () => {
  let app: FastifyInstance;
  let projectA: FixtureProject;
  let projectB: FixtureProject;
  const originalRegistry = process.env.FLEX_OBS_REGISTRY;

  beforeAll(async () => {
    projectA = await createFixtureProject();
    projectB = await createFixtureProject();
    // projectB has no .companion/state.json — state_json_present must read false.
    const fs = await import('node:fs/promises');
    await fs.rm(path.join(projectB.dir, '.companion', 'state.json'), { force: true });

    const registryPath = await writeRegistry(projectA.dir, [
      { id: 'demo-a', project_dir: projectA.dir, color: '#ff0000' },
      { id: 'demo-b', project_dir: projectB.dir, color: '#00ff00' },
    ]);
    process.env.FLEX_OBS_REGISTRY = registryPath;

    app = await buildServer('127.0.0.1');
  });

  afterAll(async () => {
    await app.close();
    await cleanupFixtureProject(projectA);
    await cleanupFixtureProject(projectB);
    if (originalRegistry === undefined) delete process.env.FLEX_OBS_REGISTRY;
    else process.env.FLEX_OBS_REGISTRY = originalRegistry;
  });

  it('returns 200 with both registered repos, shaped, against real fixture data', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/repos' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { generated_at: string; repos: unknown[] };
    expect(typeof body.generated_at).toBe('string');
    expect(Array.isArray(body.repos)).toBe(true);
    expect(body.repos).toHaveLength(2);

    const byId = Object.fromEntries((body.repos as Array<Record<string, unknown>>).map((r) => [r.id, r]));
    expect(byId['demo-a']).toMatchObject({
      id: 'demo-a',
      project_dir: projectA.dir,
      color: '#ff0000',
      registered: true,
      state_json_present: true,
    });
    expect(byId['demo-b']).toMatchObject({
      id: 'demo-b',
      project_dir: projectB.dir,
      color: '#00ff00',
      registered: true,
      state_json_present: false,
    });
  });

  it('failure-shaped: an absent/unreadable registry file yields an empty list, not a crash', async () => {
    process.env.FLEX_OBS_REGISTRY = path.join(projectA.dir, 'does-not-exist-registry.json');
    const res = await app.inject({ method: 'GET', url: '/api/repos' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { repos: unknown[] };
    expect(body.repos).toEqual([]);
  });
});
