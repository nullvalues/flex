import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../src/server.js';
import {
  createFixtureProject,
  cleanupFixtureProject,
  writeRegistry,
  type FixtureProject,
} from './fixtures/project.js';

describe('GET /api/repos/:id/context', () => {
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

  it('returns 200 with thresholds, current tokens, and effort.db rollups against fixture data', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/repos/demo-a/context' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as {
      repo_id: string;
      current: Record<string, unknown>;
      thresholds: Array<Record<string, unknown>>;
      waypoints: Array<Record<string, unknown>>;
      effort_summary: { total_attempts: number; by_phase: Array<Record<string, unknown>> };
      spend_outliers: { count: number; entries: unknown[] };
    };

    expect(body.repo_id).toBe('demo-a');

    // current field: state.json's context_current_tokens (42000), fresh
    // recorded_at -> not display-stale.
    expect(body.current.tokens).toBe(42000);
    expect(body.current.stale).toBe(false);
    expect(typeof body.current.recorded_at).toBe('string');

    // thresholds: story_spend_threshold overridden to 100000 in fixture state.json.
    const byName = Object.fromEntries(body.thresholds.map((t) => [t.name, t]));
    expect(byName.story_spend_threshold).toMatchObject({ value: 100000, source: 'state.json' });
    expect(byName.context_budget_threshold).toMatchObject({ value: 120000, source: 'state.json' });
    expect(byName.flex_factor).toMatchObject({ value: 1.0, source: 'story-frontmatter' });

    // effort.db rollup: 3 seeded rows, but 'seed-miner' is a NON_BUILD_ROLE
    // (INFRA-309) and must be excluded from total_attempts.
    expect(body.effort_summary.total_attempts).toBe(2);

    // waypoints: 100 max, DESC by ts; the 130000-token row is well above the
    // 100000 story-spend threshold (over_spend_band + delta populated).
    expect(body.waypoints.length).toBe(2);
    const overBand = body.waypoints.find((w) => w.tokens === 130000);
    expect(overBand).toMatchObject({
      story_id: 'DEMO-001',
      over_spend_band: true,
      delta_above_spend_threshold: 30000,
    });

    // spend outliers: floor is 100000 * 1.1 = 110000; only the 130000 row qualifies.
    expect(body.spend_outliers.count).toBe(1);
    expect(body.spend_outliers.entries).toHaveLength(1);
    expect(body.spend_outliers.entries[0]).toMatchObject({ tokens_total: 130000, story_id: 'DEMO-001' });
  });

  it('failure-shaped: an unregistered repo id returns 404, not a crash', async () => {
    const res = await app.inject({ method: 'GET', url: '/api/repos/does-not-exist/context' });
    expect(res.statusCode).toBe(404);
    expect(res.json()).toEqual({ error: 'repo not found', id: 'does-not-exist' });
  });
});
