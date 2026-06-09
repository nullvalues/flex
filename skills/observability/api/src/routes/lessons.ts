import type { FastifyInstance } from 'fastify';
import * as path from 'node:path';
import { readRegistry } from '../registry.js';
import { parseLessons, applyPromotionFilter, type Lesson } from '../parsers/lessons.js';

// ---------------------------------------------------------------------------
// In-process cache (2-second TTL per repo_id)
// ---------------------------------------------------------------------------

interface CacheEntry {
  ts: number;
  data: LessonsOut;
}

interface LessonsOut {
  repo_id: string;
  generated_at: string;
  lessons: Lesson[];
}

const cache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 2000;

// ---------------------------------------------------------------------------
// Route registration
// ---------------------------------------------------------------------------

export async function registerLessonsRoutes(app: FastifyInstance): Promise<void> {
  app.get<{ Params: { id: string } }>('/api/repos/:id/lessons', async (request, reply) => {
    const { id } = request.params;

    // Resolve repo in registry
    const registry = await readRegistry();
    const repo = registry.repos.find((r) => r.id === id);

    if (!repo) {
      reply.code(404).header('Content-Type', 'application/json');
      return { error: 'repo not found', id };
    }

    // Check cache
    const now = Date.now();
    const cached = cache.get(id);
    if (cached && now - cached.ts < CACHE_TTL_MS) {
      reply.header('Content-Type', 'application/json');
      return cached.data;
    }

    const lessonsPath = path.join(repo.project_dir, 'lessons', 'lessons.json');
    const rawLessons = await parseLessons(lessonsPath);
    const lessons = applyPromotionFilter(rawLessons);

    const data: LessonsOut = {
      repo_id: id,
      generated_at: new Date().toISOString(),
      lessons,
    };

    cache.set(id, { ts: now, data });

    reply.header('Content-Type', 'application/json');
    return data;
  });
}
