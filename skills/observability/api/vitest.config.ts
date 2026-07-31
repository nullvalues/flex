import { defineConfig } from 'vitest/config';

// INFRA-312: scoped route-smoke test runner for the observability API
// workspace. Node environment (no DOM) — these are Fastify `inject()`-based
// route tests, not browser tests. `cacheDir` pins Vite/vitest's own
// dependency-optimization + results cache to a single, precisely-gitignored
// path (see skills/observability/api/.gitignore) rather than the default
// `node_modules/.vite`, which the prior INFRA-312 attempt left untracked and
// broke `tests/pairmode/test_vendored_payload_tracked.py`.
export default defineConfig({
  cacheDir: 'node_modules/.vitest-cache',
  test: {
    environment: 'node',
    // Tests live outside src/ (tsconfig.json's rootDir/include) so `tsc`
    // (the `build` script) never type-checks vitest-only test code — a
    // separate concern from the compiled server payload.
    include: ['tests/**/*.test.ts'],
    passWithNoTests: false,
  },
});
