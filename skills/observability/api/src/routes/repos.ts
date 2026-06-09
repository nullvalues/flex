import type { FastifyInstance } from 'fastify';
import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import { readRegistry } from '../registry.js';

interface RepoOut {
  id: string;
  project_dir: string;
  color: string;
  registered: boolean;
  state_json_present: boolean;
}

async function fileReadable(p: string): Promise<boolean> {
  try {
    await fs.access(p, fs.constants.R_OK);
    return true;
  } catch {
    return false;
  }
}

export async function registerReposRoutes(app: FastifyInstance): Promise<void> {
  app.get('/api/repos', async (_request, reply) => {
    const registry = await readRegistry();
    const repos: RepoOut[] = [];
    for (const r of registry.repos) {
      const statePath = path.join(r.project_dir, '.companion', 'state.json');
      const present = await fileReadable(statePath);
      repos.push({
        id: r.id,
        project_dir: r.project_dir,
        color: r.color,
        registered: true,
        state_json_present: present,
      });
    }
    reply.header('Content-Type', 'application/json');
    return {
      generated_at: new Date().toISOString(),
      repos,
    };
  });
}
