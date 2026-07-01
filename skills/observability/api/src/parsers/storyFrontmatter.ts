import { promises as fs } from 'node:fs';
import * as path from 'node:path';
import * as yaml from 'js-yaml';

export interface StoryFrontmatter {
  id: string;
  rail: string;
  title: string;
  status: string;
  story_class: string;
  /** Defaults to 1.0 when absent */
  flex_factor: number;
  primary_files: string[];
  touches: string[];
}

/**
 * Parse the YAML frontmatter from a story file.
 * Returns null if the file does not exist or the frontmatter cannot be parsed.
 * Returns a partial StoryFrontmatter with "missing" status if the file doesn't exist.
 */
export async function parseStoryFrontmatter(
  projectDir: string,
  relFilePath: string,
): Promise<StoryFrontmatter | null | 'missing'> {
  const fullPath = path.join(projectDir, relFilePath);
  let content: string;
  try {
    content = await fs.readFile(fullPath, 'utf8');
  } catch {
    return 'missing';
  }

  // Extract YAML between the first and second --- delimiters
  if (!content.startsWith('---')) {
    return null;
  }

  const secondDash = content.indexOf('\n---', 3);
  if (secondDash === -1) {
    return null;
  }

  const frontmatterText = content.slice(3, secondDash).trim();

  let fm: Record<string, unknown>;
  try {
    const parsed = yaml.load(frontmatterText);
    if (!parsed || typeof parsed !== 'object') return null;
    fm = parsed as Record<string, unknown>;
  } catch {
    return null;
  }

  const id = typeof fm['id'] === 'string' ? fm['id'] : '';
  const rail = typeof fm['rail'] === 'string' ? fm['rail'] : '';
  const title = typeof fm['title'] === 'string' ? fm['title'] : '';
  const status = typeof fm['status'] === 'string' ? fm['status'] : 'unknown';
  const story_class = typeof fm['story_class'] === 'string' ? fm['story_class'] : 'code';
  let flex_factor = 1.0;
  const ffRaw = fm['flex_factor'];
  if (typeof ffRaw === 'number' && !Number.isNaN(ffRaw)) {
    flex_factor = ffRaw;
  } else if (typeof ffRaw === 'string') {
    const parsed = parseFloat(ffRaw);
    if (!Number.isNaN(parsed)) flex_factor = parsed;
  }
  const primary_files = Array.isArray(fm['primary_files'])
    ? (fm['primary_files'] as unknown[]).filter((x) => typeof x === 'string') as string[]
    : [];
  const touches = Array.isArray(fm['touches'])
    ? (fm['touches'] as unknown[]).filter((x) => typeof x === 'string') as string[]
    : [];

  return {
    id,
    rail,
    title,
    status,
    story_class,
    flex_factor,
    primary_files,
    touches,
  };
}
