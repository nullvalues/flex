import { promises as fs } from 'node:fs';
import * as path from 'node:path';

export interface PhaseIndexRow {
  /** Phase reference string, e.g. "63" or "1–7" */
  phase_ref: string;
  /** Phase file path relative to project root, e.g. "docs/phases/phase-63.md" */
  file: string | null;
  title: string;
  status: string;
  /** Checkpoint tag string, e.g. "cp63-observability-spa", or null */
  checkpoint_tag: string | null;
}

/**
 * Extract the checkpoint tag from the raw Tag column text.
 * The tag column may be:
 *   - "cp8-sync-tooling-fixes"
 *   - "[phase-8.md](phase-8.md) · cp8-sync-tooling-fixes"
 *   - "[phase-8.md](phase-8.md)"
 *   - (empty / null)
 */
function extractCheckpointTag(tagRaw: string): string | null {
  const trimmed = tagRaw.trim();
  if (!trimmed) return null;

  // Match a cp-tag token: starts with "cp" and has at least one non-whitespace char after
  // It may appear after a markdown link separated by " · "
  const cpMatch = trimmed.match(/\bcp[\w-]+/);
  if (cpMatch) {
    return cpMatch[0];
  }
  return null;
}

/**
 * Extract the href from the Tag column, if present.
 * Looks for markdown link text like "[phase-8.md](phase-8.md)".
 */
function extractHrefFromTag(tagRaw: string): string | null {
  // Match [anything](phase-NNN.md) pattern
  const linkMatch = tagRaw.match(/\[([^\]]+)\]\(([^)]+)\)/);
  if (linkMatch) {
    return linkMatch[2];
  }
  return null;
}

/**
 * Resolve an href from the Tag column to a project-relative file path,
 * enforcing that the resolved path stays within projectDir (path containment).
 * Returns null if the href is absent or resolves outside projectDir.
 */
function resolveFileFromHref(tagRaw: string, projectDir: string): string | null {
  const href = extractHrefFromTag(tagRaw);
  if (!href) return null;
  const safeRoot = path.resolve(projectDir);
  const candidatePath = path.resolve(projectDir, 'docs', 'phases', href);
  if (!candidatePath.startsWith(safeRoot + path.sep) && candidatePath !== safeRoot) {
    // Path traversal detected — skip this entry
    return null;
  }
  return `docs/phases/${href}`;
}

/**
 * Derive the phase file path from the phase_ref.
 * Only works for single numeric phase refs.
 */
function deriveFileFromPhaseRef(phaseRef: string): string | null {
  // Only handle simple integer refs
  if (/^\d+$/.test(phaseRef)) {
    return `docs/phases/phase-${phaseRef}.md`;
  }
  return null;
}

/**
 * Parse the phases table from docs/phases/index.md.
 * Returns an array of PhaseIndexRow for each data row in the table.
 * Returns [] if the file does not exist.
 */
export async function parsePhaseIndex(projectDir: string): Promise<PhaseIndexRow[]> {
  const indexPath = path.join(projectDir, 'docs', 'phases', 'index.md');
  let content: string;
  try {
    content = await fs.readFile(indexPath, 'utf8');
  } catch {
    return [];
  }

  const rows: PhaseIndexRow[] = [];
  const lines = content.split('\n');

  let inTable = false;
  let headerSeen = false;
  let separatorSeen = false;

  for (const line of lines) {
    const trimmed = line.trim();

    // Detect the header row: contains Phase, Title, Status, Tag columns
    if (!inTable && trimmed.startsWith('|')) {
      // Check if this looks like the phase table header
      if (/\|\s*Phase\s*\|/i.test(trimmed)) {
        inTable = true;
        headerSeen = true;
        continue;
      }
    }

    if (!inTable) continue;

    if (headerSeen && !separatorSeen) {
      // Separator row like |---|---|---|---|
      if (/^\|[\s\-|]+\|$/.test(trimmed)) {
        separatorSeen = true;
        continue;
      }
    }

    if (!separatorSeen) continue;

    // Data row
    if (!trimmed.startsWith('|')) {
      if (trimmed === '') continue; // blank/whitespace-only divider row — skip
      break;                        // non-pipe non-blank (heading etc.) — stop
    }

    // Split on | and trim
    const cols = trimmed.split('|').map((c) => c.trim()).filter((_, i, arr) => i > 0 && i < arr.length - 1);

    if (cols.length < 4) continue;

    const phaseRefRaw = cols[0];
    const titleRaw = cols[1];
    const statusRaw = cols[2];
    const tagRaw = cols[3] ?? '';

    const phaseRef = phaseRefRaw.trim();
    if (!phaseRef) continue;

    const title = titleRaw.trim();
    const status = statusRaw.trim() || 'unknown';

    // Determine checkpoint_tag
    const checkpoint_tag = extractCheckpointTag(tagRaw);

    // Determine file: prefer link in tag column (with path containment), otherwise derive from phase_ref
    const fileFromTag = resolveFileFromHref(tagRaw, projectDir);
    const file = fileFromTag ?? deriveFileFromPhaseRef(phaseRef);

    rows.push({
      phase_ref: phaseRef,
      file,
      title,
      status,
      checkpoint_tag,
    });
  }

  return rows;
}
