import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import * as yaml from 'js-yaml';

export interface PhaseDocStoryRow {
  /** Story ID, e.g. "INFRA-157" */
  id: string;
  title: string;
  status: string;
}

export interface PhaseDocResult {
  /** Era string from YAML frontmatter, e.g. "002", or null */
  era: string | null;
  stories: PhaseDocStoryRow[];
  /** Story IDs mentioned in the ## Deferred stories section */
  deferred: string[];
}

/**
 * Parse a phase doc file.
 * Returns null if the file cannot be read.
 */
export async function parsePhaseDoc(
  projectDir: string,
  relFilePath: string,
): Promise<PhaseDocResult | null> {
  const fullPath = path.join(projectDir, relFilePath);
  let content: string;
  try {
    content = await fs.readFile(fullPath, 'utf8');
  } catch {
    return null;
  }

  // Parse YAML frontmatter between first and second ---
  let era: string | null = null;
  let bodyStart = 0;

  if (content.startsWith('---')) {
    const secondDash = content.indexOf('\n---', 3);
    if (secondDash !== -1) {
      const frontmatterText = content.slice(3, secondDash).trim();
      try {
        const fm = yaml.load(frontmatterText) as Record<string, unknown>;
        if (fm && typeof fm === 'object' && 'era' in fm) {
          const eraVal = fm['era'];
          era =
            eraVal == null
              ? null
              : typeof eraVal === 'number'
                ? String(eraVal).padStart(3, '0')
                : String(eraVal);
        }
      } catch {
        // ignore frontmatter parse errors
      }
      bodyStart = secondDash + 4; // skip past the closing ---\n
    }
  }

  const body = content.slice(bodyStart);
  const lines = body.split('\n');

  const stories: PhaseDocStoryRow[] = [];
  const deferred: string[] = [];

  let inStoriesTable = false;
  let storiesHeaderSeen = false;
  let storiesSepSeen = false;

  let inDeferred = false;

  for (const line of lines) {
    const trimmed = line.trim();

    // Detect section headers
    if (trimmed.startsWith('## ')) {
      const heading = trimmed.slice(3).trim().toLowerCase();
      inStoriesTable = false;
      storiesHeaderSeen = false;
      storiesSepSeen = false;

      if (heading === 'stories') {
        inStoriesTable = true;
        inDeferred = false;
      } else if (heading === 'deferred stories') {
        inDeferred = true;
      } else {
        inDeferred = false;
      }
      continue;
    }

    if (inStoriesTable) {
      // Skip blank lines within a table context (they appear between ## heading and table)
      if (trimmed === '') continue;

      if (!trimmed.startsWith('|')) {
        // Non-blank, non-pipe line: table ended
        inStoriesTable = false;
        continue;
      }

      if (!storiesHeaderSeen) {
        // First pipe row is the header
        if (/\|\s*ID\s*\|/i.test(trimmed)) {
          storiesHeaderSeen = true;
        }
        continue;
      }

      if (!storiesSepSeen) {
        // Separator row
        if (/^\|[\s\-|]+\|$/.test(trimmed)) {
          storiesSepSeen = true;
        }
        continue;
      }

      // Data row
      const cols = trimmed.split('|').map((c) => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);
      if (cols.length < 3) continue;

      const id = cols[0].replace(/`/g, '').trim();
      const title = cols[1].replace(/`/g, '').trim();
      const status = cols[2].trim() || 'unknown';

      if (id) {
        stories.push({ id, title, status });
      }
      continue;
    }

    if (inDeferred) {
      // Extract story IDs (pattern: RAIL-NNN) from the deferred section text
      const idMatches = trimmed.matchAll(/\b([A-Z]+-\d+)\b/g);
      for (const m of idMatches) {
        if (!deferred.includes(m[1])) {
          deferred.push(m[1]);
        }
      }
    }
  }

  return { era, stories, deferred };
}
