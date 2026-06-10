import { useContext, ApiError } from '../api/client';
import { Card, CardHeader, CardTitle, CardBody } from './ui/Card';
import { Badge } from './ui/Badge';
import { Skeleton } from './ui/Skeleton';
import { Progress } from './ui/Progress';
import { Separator } from './ui/Separator';

interface Props {
  repoId: string;
}

function fmtTokens(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

function fmtTs(ts: string | null | undefined): string {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return ts;
    return d.toLocaleString();
  } catch {
    return ts ?? '—';
  }
}

export function ContextMetrics({ repoId }: Props) {
  const { data, isLoading, error } = useContext(repoId);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Context</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-2 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        </CardBody>
      </Card>
    );
  }

  if (error) {
    const apiErr = error as ApiError;
    return (
      <Card>
        <CardHeader>
          <CardTitle>Context</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-red-600 dark:text-red-300">
            Error fetching context: HTTP {apiErr.status ?? '?'} — {apiErr.message}
          </p>
        </CardBody>
      </Card>
    );
  }

  if (!data) {
    return null;
  }

  const threshold = data.thresholds.find((t) => t.name === 'context_budget_threshold');
  const overrun = data.thresholds.find((t) => t.name === 'context_budget_overrun_pct');
  const flexFactor = data.thresholds.find((t) => t.name === 'flex_factor');
  const thresholdValue = threshold?.value ?? 120000;
  const overrunPct = overrun?.value ?? 0.1;
  const flexFactorValue = flexFactor?.value ?? 1.0;
  const effectiveCeiling = Math.round(thresholdValue * (1 + overrunPct) * flexFactorValue);

  const current = data.current;
  const currentTokens = current.tokens ?? 0;
  const ratio = thresholdValue > 0 ? currentTokens / thresholdValue : 0;
  const progressTone = ratio >= 1.0 ? 'danger' : ratio >= 0.85 ? 'warning' : 'normal';

  const recentWaypoints = data.waypoints.slice(0, 10);
  const recentPhases = data.effort_summary.by_phase.slice(0, 5);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Context</CardTitle>
      </CardHeader>
      <CardBody>
        <div className="space-y-3">
          {/* Current token count + progress */}
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="text-slate-600 dark:text-slate-300">
                <span className="font-mono">{fmtTokens(current.tokens)}</span>
                <span className="text-slate-400"> / </span>
                <span className="font-mono">{fmtTokens(thresholdValue)}</span>
                <span className="ml-1 text-slate-400">(ceil {fmtTokens(effectiveCeiling)})</span>
              </span>
              <div className="flex items-center gap-1">
                {current.stale && <Badge tone="warning">stale</Badge>}
                {current.story_id && (
                  <span className="font-mono text-[10px] text-slate-500">
                    {current.story_id}
                  </span>
                )}
              </div>
            </div>
            <Progress value={currentTokens} max={thresholdValue} tone={progressTone} />
            <div className="mt-1 text-[10px] text-slate-500">
              recorded {fmtTs(current.recorded_at)}
              {current.age_seconds != null && ` (${current.age_seconds}s ago)`}
            </div>
          </div>

          <Separator />

          {/* Thresholds table */}
          <div>
            <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Thresholds
            </h4>
            <table className="w-full table-fixed text-xs">
              <thead>
                <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
                  <th className="w-1/2 py-1">name</th>
                  <th className="w-1/4 py-1 text-right">value</th>
                  <th className="w-1/4 py-1 text-right">source</th>
                </tr>
              </thead>
              <tbody>
                {data.thresholds.map((t) => (
                  <tr key={t.name} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1 font-mono text-[11px] text-slate-700 dark:text-slate-200">
                      {t.name}
                    </td>
                    <td className="py-1 text-right font-mono text-[11px]">
                      {t.value}
                    </td>
                    <td className="py-1 text-right">
                      <Badge tone={t.source === 'state.json' ? 'info' : 'muted'}>{t.source}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Separator />

          {/* Waypoints */}
          <div>
            <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Waypoints (last 10)
            </h4>
            {recentWaypoints.length === 0 ? (
              <p className="text-[11px] text-slate-500">No waypoints recorded yet.</p>
            ) : (
              <table className="w-full table-fixed text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
                    <th className="w-1/3 py-1">ts</th>
                    <th className="w-1/6 py-1 text-right">tokens</th>
                    <th className="w-1/3 py-1">story</th>
                    <th className="w-1/6 py-1 text-right">outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {recentWaypoints.map((w, i) => (
                    <tr
                      key={`${w.ts}-${i}`}
                      className="border-t border-slate-100 dark:border-slate-800"
                    >
                      <td className="truncate py-1 font-mono text-[10px]">{fmtTs(w.ts)}</td>
                      <td className="py-1 text-right font-mono text-[11px]">
                        {fmtTokens(w.tokens)}
                      </td>
                      <td className="truncate py-1 font-mono text-[10px]">{w.story_id ?? '—'}</td>
                      <td className="py-1 text-right">
                        {w.outcome && (
                          <Badge tone={w.outcome === 'PASS' ? 'success' : 'warning'}>
                            {w.outcome}
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <Separator />

          {/* Effort summary */}
          <div>
            <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Effort
            </h4>
            <p className="mb-1 text-xs text-slate-600 dark:text-slate-300">
              Total attempts:{' '}
              <span className="font-mono">{data.effort_summary.total_attempts}</span>
            </p>
            {recentPhases.length > 0 && (
              <table className="w-full table-fixed text-xs">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
                    <th className="w-1/3 py-1">phase</th>
                    <th className="w-1/4 py-1 text-right">attempts</th>
                    <th className="w-1/4 py-1 text-right">median</th>
                    <th className="w-1/4 py-1 text-right">p90</th>
                  </tr>
                </thead>
                <tbody>
                  {recentPhases.map((p) => (
                    <tr key={p.phase} className="border-t border-slate-100 dark:border-slate-800">
                      <td className="py-1 font-mono text-[11px]">{p.phase}</td>
                      <td className="py-1 text-right font-mono text-[11px]">{p.attempts}</td>
                      <td className="py-1 text-right font-mono text-[11px]">
                        {fmtTokens(p.median_tokens)}
                      </td>
                      <td className="py-1 text-right font-mono text-[11px]">
                        {fmtTokens(p.p90_tokens)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {data.misses.count > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Near-miss blocks ({data.misses.count})
                </h4>
                <ul className="space-y-0.5 text-[11px]">
                  {data.misses.entries.slice(0, 5).map((m, i) => (
                    <li key={`${m.ts}-${i}`} className="font-mono text-slate-600 dark:text-slate-300">
                      {fmtTs(m.ts)} · {fmtTokens(m.tokens_at_block)} · {m.story_id ?? '—'}
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>
      </CardBody>
    </Card>
  );
}

export default ContextMetrics;
