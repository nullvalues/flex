import { promises as fs } from 'node:fs';
import * as path from 'node:path';

/**
 * Read `.companion/state.json` from the given project directory.
 * Returns {} if the file is absent, unreadable, or unparseable.
 * Never throws.
 */
export async function readStateJson(
  projectDir: string,
): Promise<Record<string, unknown>> {
  const statePath = path.join(projectDir, '.companion', 'state.json');
  try {
    const raw = await fs.readFile(statePath, 'utf8');
    const parsed: unknown = JSON.parse(raw);
    if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return {};
  } catch {
    return {};
  }
}
