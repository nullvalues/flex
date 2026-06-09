import type { FastifyInstance } from 'fastify';
import { promises as fs } from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { firstHeading } from '../parsers/markdownMeta.js';

// ---------------------------------------------------------------------------
// Memory shapes
// ---------------------------------------------------------------------------

interface MemoryFile {
  filename: string;
  first_heading: string;
  modified_at: string;
  abs_path: string;
  size_bytes: number;
}

interface ProjectMemories {
  project_hash: string;
  memories: MemoryFile[];
}

interface MemoriesOut {
  generated_at: string;
  projects: ProjectMemories[];
}

// ---------------------------------------------------------------------------
// Policy shapes
// ---------------------------------------------------------------------------

interface PolicyFile {
  filename: string;
  first_heading: string;
  modified_at: string;
  abs_path: string;
  size_bytes: number;
}

interface PoliciesOut {
  generated_at: string;
  policies: PolicyFile[];
}

// ---------------------------------------------------------------------------
// Helper: list subdirectory entries safely
// ---------------------------------------------------------------------------

async function listDir(dirPath: string): Promise<string[]> {
  try {
    return await fs.readdir(dirPath);
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Helper: read file content safely (returns null on error)
// ---------------------------------------------------------------------------

async function safeReadFile(filePath: string): Promise<string | null> {
  try {
    return await fs.readFile(filePath, 'utf8');
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Helper: stat a file safely (returns null on error)
// ---------------------------------------------------------------------------

async function safeStat(filePath: string): Promise<{ mtime: Date; size: number } | null> {
  try {
    const st = await fs.stat(filePath);
    return { mtime: st.mtime, size: st.size };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Route registration
// ---------------------------------------------------------------------------

export async function registerUserRoutes(app: FastifyInstance): Promise<void> {
  // GET /api/user/memories
  app.get('/api/user/memories', async (_request, reply) => {
    const generated_at = new Date().toISOString();
    const projectsRoot = path.join(os.homedir(), '.claude', 'projects');

    const projectDirs = await listDir(projectsRoot);
    if (projectDirs.length === 0) {
      reply.header('Content-Type', 'application/json');
      return { generated_at, projects: [] } satisfies MemoriesOut;
    }

    const projects: ProjectMemories[] = [];

    for (const projectHash of projectDirs) {
      const memoryDir = path.join(projectsRoot, projectHash, 'memory');
      let memFiles: string[];
      try {
        memFiles = await fs.readdir(memoryDir);
      } catch {
        // No memory directory — skip this project
        continue;
      }

      const memories: MemoryFile[] = [];

      for (const filename of memFiles) {
        if (!filename.endsWith('.md')) continue;
        const absPath = path.join(memoryDir, filename);
        const [content, st] = await Promise.all([safeReadFile(absPath), safeStat(absPath)]);
        if (content === null || st === null) {
          // Permission error or vanished — skip silently
          continue;
        }
        const stem = filename.replace(/\.md$/, '');
        memories.push({
          filename,
          first_heading: firstHeading(content, stem),
          modified_at: st.mtime.toISOString(),
          abs_path: absPath,
          size_bytes: st.size,
        });
      }

      if (memories.length > 0) {
        projects.push({ project_hash: projectHash, memories });
      }
    }

    reply.header('Content-Type', 'application/json');
    return { generated_at, projects } satisfies MemoriesOut;
  });

  // GET /api/user/policies
  app.get('/api/user/policies', async (_request, reply) => {
    const generated_at = new Date().toISOString();
    const policiesDir = path.join(os.homedir(), '.claude', 'policies');

    const entries = await listDir(policiesDir);
    const policies: PolicyFile[] = [];

    for (const filename of entries) {
      if (!filename.endsWith('.md')) continue;
      const absPath = path.join(policiesDir, filename);
      const [content, st] = await Promise.all([safeReadFile(absPath), safeStat(absPath)]);
      if (content === null || st === null) {
        continue;
      }
      const stem = filename.replace(/\.md$/, '');
      policies.push({
        filename,
        first_heading: firstHeading(content, stem),
        modified_at: st.mtime.toISOString(),
        abs_path: absPath,
        size_bytes: st.size,
      });
    }

    reply.header('Content-Type', 'application/json');
    return { generated_at, policies } satisfies PoliciesOut;
  });
}
