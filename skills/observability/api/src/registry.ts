import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';

export interface RegistryRepo {
  id: string;
  project_dir: string;
  color: string;
}

export interface Registry {
  version: number;
  repos: RegistryRepo[];
  default_port?: number;
  bind_host?: string;
}

/**
 * Resolve the registry path from FLEX_OBS_REGISTRY env var if set,
 * otherwise default to ~/.config/flex-observability/registry.json.
 */
export function registryPath(): string {
  const fromEnv = process.env.FLEX_OBS_REGISTRY;
  if (fromEnv && fromEnv.length > 0) {
    return fromEnv;
  }
  return path.join(os.homedir(), '.config', 'flex-observability', 'registry.json');
}

/**
 * Read the registry from disk. Returns an empty-registry shape if the file
 * is absent or unreadable. Never throws.
 */
export async function readRegistry(): Promise<Registry> {
  const p = registryPath();
  try {
    const raw = await fs.readFile(p, 'utf8');
    const parsed = JSON.parse(raw) as Partial<Registry>;
    const version = typeof parsed.version === 'number' ? parsed.version : 1;
    const repos = Array.isArray(parsed.repos) ? parsed.repos : [];
    const out: Registry = { version, repos };
    if (typeof parsed.default_port === 'number') {
      out.default_port = parsed.default_port;
    }
    if (typeof parsed.bind_host === 'string') {
      out.bind_host = parsed.bind_host;
    }
    return out;
  } catch {
    return { version: 1, repos: [] };
  }
}
