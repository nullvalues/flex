import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useRepos, ApiError } from './api/client';
import { RepoPanel } from './components/RepoPanel';
import { Badge } from './components/ui/Badge';
import { Skeleton } from './components/ui/Skeleton';

function formatTime(ts: string | null): string {
  if (!ts) return 'never';
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toLocaleTimeString();
  } catch {
    return ts ?? 'never';
  }
}

function App() {
  const queryClient = useQueryClient();
  const { data, isLoading, error, dataUpdatedAt } = useRepos();

  // Selected repos: default to all known repos; allow user to pin/unpin.
  const [pinned, setPinned] = useState<Record<string, boolean>>({});

  const allRepos = useMemo(() => data?.repos ?? [], [data]);

  const visibleRepos = useMemo(() => {
    if (allRepos.length === 0) return [];
    // If user hasn't touched the selector, show everything.
    const touched = Object.keys(pinned).length > 0;
    if (!touched) return allRepos;
    return allRepos.filter((r) => pinned[r.id] !== false);
  }, [allRepos, pinned]);

  const togglePin = (id: string) => {
    setPinned((prev) => ({ ...prev, [id]: !(prev[id] ?? true) }));
  };

  const lastRefreshed = dataUpdatedAt ? new Date(dataUpdatedAt).toISOString() : null;

  const handleRefresh = () => {
    void queryClient.invalidateQueries();
  };

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold">flex observability</h1>
          <span className="text-[11px] text-slate-500">
            last refreshed: {formatTime(lastRefreshed)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Repo selector */}
          <div className="flex flex-wrap items-center gap-1">
            {allRepos.map((r) => {
              const active = pinned[r.id] !== false;
              return (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => togglePin(r.id)}
                  className={
                    'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs ' +
                    (active
                      ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-200'
                      : 'border-slate-200 bg-white text-slate-500 dark:border-slate-700 dark:bg-slate-900')
                  }
                  aria-pressed={active}
                  title={active ? 'Click to hide' : 'Click to show'}
                >
                  <span
                    aria-hidden="true"
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: r.color || '#94a3b8' }}
                  />
                  {r.id}
                </button>
              );
            })}
          </div>
          <button
            type="button"
            onClick={handleRefresh}
            className="rounded-md border border-slate-200 bg-white px-2 py-0.5 text-xs hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800"
          >
            Refresh
          </button>
        </div>
      </header>

      {/* Body */}
      <main className="min-h-0 flex-1 overflow-auto p-4">
        {isLoading && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-64 w-full" />
            ))}
          </div>
        )}

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-200">
            <p className="font-semibold">Failed to load repos</p>
            <p className="text-xs">
              HTTP {(error as ApiError).status ?? '?'} — {(error as ApiError).message}
            </p>
          </div>
        )}

        {!isLoading && !error && visibleRepos.length === 0 && (
          <div className="rounded-md border border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900">
            <p className="font-semibold">No repos registered.</p>
            <p className="mt-1 text-xs text-slate-500">
              Run{' '}
              <code className="rounded bg-slate-100 px-1 dark:bg-slate-800">
                flex-observability register --project-dir DIR
              </code>{' '}
              to add one.
            </p>
          </div>
        )}

        {!isLoading && !error && visibleRepos.length > 0 && (
          <div
            className="grid gap-3"
            style={{
              // Side-by-side on wide viewports, stacked on narrow.
              gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
            }}
          >
            {visibleRepos.map((r) => (
              <div key={r.id} className="min-h-[480px]">
                <RepoPanel repo={r} />
              </div>
            ))}
            {/* Stacked fallback for narrow viewports — display in DOM order;
                Tailwind handles via the auto-fill min-width above. */}
            <div className="hidden sm:block" aria-hidden="true">
              {/* placeholder to keep grid balanced */}
            </div>
            <Badge tone="muted" className="hidden">
              {visibleRepos.length} repos
            </Badge>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
