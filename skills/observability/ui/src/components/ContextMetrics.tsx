import { useContext, ApiError } from '../api/client';
import type { ResolverStateDoc } from '../api/client';
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

function shortFile(f: string | null): string {
  if (!f) return '—';
  const parts = f.split('/');
  return parts[parts.length - 1] ?? f;
}

// ---------------------------------------------------------------------------
// Build loop panel — next-action + position from resolver state (OBS-002)
// ---------------------------------------------------------------------------

function BuildLoopPanel({ rs }: { rs: ResolverStateDoc }) {
  const action = rs.action;
  const pos = rs.position;

  const gateOk = pos.gate_stub.ok && pos.gate_schema.ok && pos.gate_auth.ok;
  const blockedGates = [
    !pos.gate_stub.ok && `stub: ${pos.gate_stub.blocked_reason}`,
    !pos.gate_schema.ok && `schema: ${pos.gate_schema.blocked_reason}`,
    !pos.gate_auth.ok && `auth: ${pos.gate_auth.blocked_reason}`,
  ].filter(Boolean);

  return (
    <div className="space-y-2">
      {/* Next action */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wide">
          next-action
        </span>
        <Badge tone="info">{action.action}</Badge>
        {action.scalar && (
          <span className="font-mono text-[11px] text-slate-600 dark:text-slate-300">
            {action.scalar}
          </span>
        )}
        {action.model && (
          <span className="font-mono text-[10px] text-slate-400">[{action.model}]</span>
        )}
      </div>
      {action.reason && (
        <p className="text-[10px] text-slate-500 italic">{action.reason}</p>
      )}

      {/* Position */}
      <table className="w-full table-fixed text-xs">
        <tbody>
          <tr className="border-t border-slate-100 dark:border-slate-800">
            <td className="py-0.5 text-[10px] text-slate-400 w-2/5">phase</td>
            <td className="py-0.5 font-mono text-[11px] truncate">{shortFile(pos.active_phase_file)}</td>
          </tr>
          <tr className="border-t border-slate-100 dark:border-slate-800">
            <td className="py-0.5 text-[10px] text-slate-400">next story</td>
            <td className="py-0.5 font-mono text-[11px]">{pos.next_story_id ?? '—'}</td>
          </tr>
          <tr className="border-t border-slate-100 dark:border-slate-800">
            <td className="py-0.5 text-[10px] text-slate-400">attempts</td>
            <td className="py-0.5 font-mono text-[11px]">{pos.attempt_count}</td>
          </tr>
          <tr className="border-t border-slate-100 dark:border-slate-800">
            <td className="py-0.5 text-[10px] text-slate-400">last outcome</td>
            <td className="py-0.5 font-mono text-[11px]">{pos.last_attempt_outcome || '—'}</td>
          </tr>
          {pos.needs_spec && (
            <tr className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-0.5 text-[10px] text-slate-400">needs spec</td>
              <td className="py-0.5">
                <Badge tone="warning">yes</Badge>
              </td>
            </tr>
          )}
          {pos.checkpoint_step.length > 0 && (
            <tr className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-0.5 text-[10px] text-slate-400">checkpoint</td>
              <td className="py-0.5 font-mono text-[10px] truncate">
                {pos.checkpoint_step.join(' → ')}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {/* Gates */}
      <div className="flex flex-wrap items-center gap-1">
        <span className="text-[10px] text-slate-400">gates:</span>
        {gateOk ? (
          <Badge tone="success">all clear</Badge>
        ) : (
          blockedGates.map((msg, i) => (
            <Badge key={i} tone="warning">{msg as string}</Badge>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Resolver index panel (OBS-002, CER-056)
// ---------------------------------------------------------------------------

function ResolverIndexPanel({ rs }: { rs: ResolverStateDoc }) {
  if (rs.index.length === 0) return null;

  return (
    <div>
      <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        Phase index
      </h4>
      <table className="w-full table-fixed text-xs">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
            <th className="w-1/4 py-1">ref</th>
            <th className="w-1/2 py-1">status</th>
            <th className="w-1/4 py-1 text-right">active</th>
          </tr>
        </thead>
        <tbody>
          {rs.index.map((entry) => (
            <tr key={entry.phase_ref} className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-0.5 font-mono text-[11px]">{entry.phase_ref}</td>
              <td className="py-0.5 text-[11px] text-slate-600 dark:text-slate-300">
                {entry.status}
              </td>
              <td className="py-0.5 text-right">
                <Badge tone={entry.active ? 'success' : 'muted'}>
                  {entry.active ? 'yes' : 'no'}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-role effort panel (OBS-002)
// ---------------------------------------------------------------------------

function RoleEffortPanel({ rs }: { rs: ResolverStateDoc }) {
  const entries = Object.entries(rs.effort_by_role);
  if (entries.length === 0) return null;

  return (
    <div>
      <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
        Effort by role
      </h4>
      <table className="w-full table-fixed text-xs">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wide text-slate-400">
            <th className="w-1/3 py-1">role</th>
            <th className="w-1/3 py-1 text-right">count</th>
            <th className="w-1/3 py-1 text-right">median</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([role, entry]) => (
            <tr key={role} className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-1 font-mono text-[11px]">{role}</td>
              <td className="py-1 text-right font-mono text-[11px]">{entry.count}</td>
              <td className="py-1 text-right font-mono text-[11px]">
                {fmtTokens(entry.median_tokens)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

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
  const rs = data.resolver_state;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Context</CardTitle>
      </CardHeader>
      <CardBody>
        <div className="space-y-3">
          {/* Build loop — resolver state (OBS-002) */}
          {rs && (
            <>
              <div>
                <h4 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Build loop
                </h4>
                <BuildLoopPanel rs={rs} />
              </div>
              <Separator />
            </>
          )}

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
                  <th className="w-5/12 py-1">name</th>
                  <th className="w-2/12 py-1 text-right">value</th>
                  <th className="w-5/12 py-1 text-right">source</th>
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
                      {t.provenance ? (
                        <span className="text-[10px] text-slate-500 italic">{t.provenance}</span>
                      ) : (
                        <Badge tone={t.source === 'state.json' ? 'info' : 'muted'}>{t.source}</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Separator />

          {/* Waypoints (per-leaf-worker, agent_role keyed) */}
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
                    <th className="w-1/4 py-1">ts</th>
                    <th className="w-1/6 py-1 text-right">tokens</th>
                    <th className="w-1/4 py-1">role</th>
                    <th className="w-1/4 py-1">story</th>
                    <th className="w-1/12 py-1 text-right">out</th>
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
                      <td className="truncate py-1 font-mono text-[10px] text-slate-500">
                        {w.agent_role ?? '—'}
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

          {/* Effort by role (OBS-002) */}
          {rs && rs.effort_by_role && Object.keys(rs.effort_by_role).length > 0 && (
            <>
              <Separator />
              <RoleEffortPanel rs={rs} />
            </>
          )}

          {/* Effort totals (from effort.db, unchanged) */}
          {data.effort_summary.total_attempts > 0 && (
            <>
              <Separator />
              <div>
                <h4 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  Effort totals
                </h4>
                <p className="text-xs text-slate-600 dark:text-slate-300">
                  Total attempts:{' '}
                  <span className="font-mono">{data.effort_summary.total_attempts}</span>
                </p>
              </div>
            </>
          )}

          {/* Resolver index (OBS-002, CER-056) */}
          {rs && rs.index.length > 0 && (
            <>
              <Separator />
              <ResolverIndexPanel rs={rs} />
            </>
          )}

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
