import type { FastifyInstance } from 'fastify';
import { readRegistry } from '../registry.js';
import { parsePhaseIndex } from '../parsers/phaseIndex.js';
import { parsePhaseDoc } from '../parsers/phaseDoc.js';
import { parseStoryFrontmatter } from '../parsers/storyFrontmatter.js';
import { readResolverState, type ResolverStateDoc } from '../readers/resolverState.js';

// ---------------------------------------------------------------------------
// Output shapes
// ---------------------------------------------------------------------------

interface StoryOut {
  id: string;
  rail: string;
  title: string;
  status: string;
  story_class: string;
  flex_factor: number;
  primary_files: string[];
  touches: string[];
}

interface PhaseOut {
  phase_ref: string;
  file: string | null;
  title: string | null;
  status: string;
  checkpoint_tag: string | null;
  era: string | null;
  stories: StoryOut[];
  deferred: string[];
}

interface SystemOut {
  repo_id: string;
  generated_at: string;
  phases: PhaseOut[];
  resolver_state: ResolverStateDoc | null;
}

// ---------------------------------------------------------------------------
// Simple in-process cache (2 second TTL per repo_id)
// ---------------------------------------------------------------------------

interface CacheEntry {
  ts: number;
  data: SystemOut;
}

const cache = new Map<string, CacheEntry>();
const CACHE_TTL_MS = 2000;

// ---------------------------------------------------------------------------
// Story path resolver
// ---------------------------------------------------------------------------

/**
 * Given a story ID like "INFRA-157", return the relative path
 * "docs/stories/INFRA/INFRA-157.md".
 */
function storyIdToPath(storyId: string): string {
  // Extract rail prefix: everything before the last hyphen+digits
  const match = storyId.match(/^([A-Z]+)-(\d+)$/);
  if (!match) {
    // Fallback: use the ID as the rail directory
    return `docs/stories/${storyId}/${storyId}.md`;
  }
  const rail = match[1];
  return `docs/stories/${rail}/${storyId}.md`;
}

// ---------------------------------------------------------------------------
// Build the system-of-record payload for one repo
// ---------------------------------------------------------------------------

async function buildSystemPayload(projectDir: string, repoId: string): Promise<SystemOut> {
  const generated_at = new Date().toISOString();

  // 1. Parse phase index
  const indexRows = await parsePhaseIndex(projectDir);

  if (indexRows.length === 0) {
    const resolver_state = readResolverState(projectDir);
    return { repo_id: repoId, generated_at, phases: [], resolver_state };
  }

  // 2. Sort by numeric phase_ref ascending, non-numeric refs sort to end
  const sorted = [...indexRows].sort((a, b) => {
    const na = parseInt(a.phase_ref, 10);
    const nb = parseInt(b.phase_ref, 10);
    if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
    if (Number.isFinite(na)) return -1;
    if (Number.isFinite(nb)) return 1;
    return a.phase_ref.localeCompare(b.phase_ref);
  });

  // 3. Fan out phase doc reads
  const phases: PhaseOut[] = await Promise.all(
    sorted.map(async (row) => {
      const phaseFile = row.file;

      if (!phaseFile) {
        return {
          phase_ref: row.phase_ref,
          file: null,
          title: row.title || null,
          status: row.status || 'unknown',
          checkpoint_tag: row.checkpoint_tag,
          era: null,
          stories: [],
          deferred: [],
        };
      }

      const phaseDoc = await parsePhaseDoc(projectDir, phaseFile);

      if (!phaseDoc) {
        // Phase file listed in index but not found on disk
        return {
          phase_ref: row.phase_ref,
          file: phaseFile,
          title: row.title || null,
          status: row.status || 'unknown',
          checkpoint_tag: row.checkpoint_tag,
          era: null,
          stories: [],
          deferred: [],
        };
      }

      // 4. Fan out story reads in parallel
      const storyOuts: StoryOut[] = await Promise.all(
        phaseDoc.stories.map(async (s) => {
          const relPath = storyIdToPath(s.id);
          const fm = await parseStoryFrontmatter(projectDir, relPath);

          if (fm === 'missing') {
            // Story file listed in phase doc but not on disk
            return {
              id: s.id,
              rail: '',
              title: s.title,
              status: 'missing',
              story_class: 'code',
              flex_factor: 1.0,
              primary_files: [],
              touches: [],
            };
          }

          if (!fm) {
            // File exists but is unparseable
            return {
              id: s.id,
              rail: '',
              title: s.title,
              status: s.status,
              story_class: 'code',
              flex_factor: 1.0,
              primary_files: [],
              touches: [],
            };
          }

          return {
            id: fm.id || s.id,
            rail: fm.rail,
            title: fm.title || s.title,
            status: fm.status,
            story_class: fm.story_class,
            flex_factor: fm.flex_factor,
            primary_files: fm.primary_files,
            touches: fm.touches,
          };
        }),
      );

      return {
        phase_ref: row.phase_ref,
        file: phaseFile,
        title: row.title || null,
        status: row.status || 'unknown',
        checkpoint_tag: row.checkpoint_tag,
        era: phaseDoc.era,
        stories: storyOuts,
        deferred: phaseDoc.deferred,
      };
    }),
  );

  const resolver_state = readResolverState(projectDir);
  return { repo_id: repoId, generated_at, phases, resolver_state };
}

// ---------------------------------------------------------------------------
// Route registration
// ---------------------------------------------------------------------------

export async function registerSystemRoutes(app: FastifyInstance): Promise<void> {
  app.get<{ Params: { id: string } }>('/api/repos/:id/system', async (request, reply) => {
    const { id } = request.params;

    // Look up repo in registry
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

    const data = await buildSystemPayload(repo.project_dir, id);

    cache.set(id, { ts: now, data });

    reply.header('Content-Type', 'application/json');
    return data;
  });
}
