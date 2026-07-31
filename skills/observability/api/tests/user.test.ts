import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { promises as fsp } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import type { FastifyInstance } from 'fastify';
import { buildServer } from '../src/server.js';

// user.ts routes read directly from os.homedir() (~/.claude/{projects,policies}),
// not from a registered repo — so the fixture here is a fake $HOME rather
// than a registered-repo tree, keeping the test hermetic (INFRA-312
// Instructions §3: not the live flex repo / real operator home).
describe('GET /api/user/memories and /api/user/policies', () => {
  let app: FastifyInstance;
  let fakeHome: string;
  const originalHome = process.env.HOME;

  beforeEach(async () => {
    fakeHome = await fsp.mkdtemp(path.join(os.tmpdir(), 'flex-obs-home-'));
    app = await buildServer('127.0.0.1');
  });

  afterEach(async () => {
    await app.close();
    await fsp.rm(fakeHome, { recursive: true, force: true });
    if (originalHome === undefined) delete process.env.HOME;
    else process.env.HOME = originalHome;
  });

  it('returns 200 with real memory content, shaped, when $HOME has memory files', async () => {
    const projectHash = 'demo-project-hash';
    const memoryDir = path.join(fakeHome, '.claude', 'projects', projectHash, 'memory');
    await fsp.mkdir(memoryDir, { recursive: true });
    await fsp.writeFile(
      path.join(memoryDir, 'MEMORY.md'),
      '# Memory — demo project\n\n- a real fixture memory line\n',
      'utf8',
    );
    process.env.HOME = fakeHome;

    const res = await app.inject({ method: 'GET', url: '/api/user/memories' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { generated_at: string; projects: Array<Record<string, unknown>> };
    expect(typeof body.generated_at).toBe('string');
    expect(body.projects).toHaveLength(1);
    expect(body.projects[0].project_hash).toBe(projectHash);
    const memories = body.projects[0].memories as Array<Record<string, unknown>>;
    expect(memories).toHaveLength(1);
    expect(memories[0]).toMatchObject({
      filename: 'MEMORY.md',
      first_heading: 'Memory — demo project',
    });
    expect(memories[0].abs_path).toBeUndefined();
  });

  it('include_path=true populates abs_path (CER-043 opt-in disclosure)', async () => {
    const projectHash = 'demo-project-hash';
    const memoryDir = path.join(fakeHome, '.claude', 'projects', projectHash, 'memory');
    await fsp.mkdir(memoryDir, { recursive: true });
    await fsp.writeFile(path.join(memoryDir, 'MEMORY.md'), '# Demo\n', 'utf8');
    process.env.HOME = fakeHome;

    const res = await app.inject({ method: 'GET', url: '/api/user/memories?include_path=true' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { projects: Array<{ memories: Array<Record<string, unknown>> }> };
    expect(body.projects[0].memories[0].abs_path).toBe(path.join(memoryDir, 'MEMORY.md'));
  });

  it('returns 200 with real policy content, shaped, when $HOME has policy files', async () => {
    const policiesDir = path.join(fakeHome, '.claude', 'policies');
    await fsp.mkdir(policiesDir, { recursive: true });
    await fsp.writeFile(path.join(policiesDir, 'auth-rbac.md'), '# RBAC policy\n', 'utf8');
    process.env.HOME = fakeHome;

    const res = await app.inject({ method: 'GET', url: '/api/user/policies' });
    expect(res.statusCode).toBe(200);
    const body = res.json() as { generated_at: string; policies: Array<Record<string, unknown>> };
    expect(body.policies).toHaveLength(1);
    expect(body.policies[0]).toMatchObject({ filename: 'auth-rbac.md', first_heading: 'RBAC policy' });
  });

  it('failure-shaped: a $HOME with no .claude directory at all returns 200 with empty lists, not a crash', async () => {
    process.env.HOME = fakeHome; // freshly created, nothing under it
    const memRes = await app.inject({ method: 'GET', url: '/api/user/memories' });
    expect(memRes.statusCode).toBe(200);
    expect(memRes.json()).toMatchObject({ projects: [] });

    const polRes = await app.inject({ method: 'GET', url: '/api/user/policies' });
    expect(polRes.statusCode).toBe(200);
    expect(polRes.json()).toMatchObject({ policies: [] });
  });
});
