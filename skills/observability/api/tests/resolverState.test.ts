import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { getFlexBuildPath, readResolverState } from '../src/readers/resolverState.js';

// CER-142 / INFRA-368: getFlexBuildPath() was resolving one directory too
// high, so the path it produced (`<repo-root>/pairmode/scripts/flex_build.py`)
// never existed on disk and every call to `readResolverState` silently
// returned null. An existence assertion is the only form that distinguishes
// the broken path from the fixed one — a string-equality assertion built
// from the same `path.join` expression the source uses would pass for both.
describe('getFlexBuildPath', () => {
  it('resolves to a real flex_build.py on disk, ending in skills/pairmode/scripts/flex_build.py', () => {
    const resolved = getFlexBuildPath();

    expect(resolved.endsWith(path.join('skills', 'pairmode', 'scripts', 'flex_build.py'))).toBe(
      true,
    );
    expect(fs.existsSync(resolved)).toBe(true);
  });
});

describe('readResolverState', () => {
  it('returns a non-null object when invoked against this repo checkout', () => {
    const thisFile = fileURLToPath(import.meta.url);
    // tests/ -> api/ -> observability/ -> skills/ -> <repo-root>
    const repoRoot = path.resolve(path.dirname(thisFile), '..', '..', '..', '..');

    const result = readResolverState(repoRoot);

    expect(result).not.toBeNull();
  });
});
