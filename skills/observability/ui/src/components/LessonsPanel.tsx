import { useLessons, ApiError } from '../api/client';
import { Card, CardHeader, CardTitle, CardBody } from './ui/Card';
import { Badge } from './ui/Badge';
import { Skeleton } from './ui/Skeleton';

interface Props {
  repoId: string;
}

function truncate(s: string | undefined, n: number): string {
  if (!s) return '';
  if (s.length <= n) return s;
  return s.slice(0, n - 1) + '…';
}

export function LessonsPanel({ repoId }: Props) {
  const { data, isLoading, error } = useLessons(repoId);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Lessons</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="space-y-2">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-3/4" />
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
          <CardTitle>Lessons</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-red-600 dark:text-red-300">
            Error fetching lessons: HTTP {apiErr.status ?? '?'} — {apiErr.message}
          </p>
        </CardBody>
      </Card>
    );
  }

  if (!data || data.lessons.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Lessons</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-slate-500">No lessons recorded for this repo.</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Lessons ({data.lessons.length})</CardTitle>
      </CardHeader>
      <CardBody>
        <ul className="space-y-2">
          {data.lessons.map((l) => (
            <li
              key={l.id}
              className={
                'rounded-md border p-2 text-xs ' +
                (l.promotion_candidate
                  ? 'border-amber-400 bg-amber-50/60 dark:bg-amber-900/10'
                  : 'border-slate-200 dark:border-slate-800')
              }
            >
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">
                  {l.id}
                </span>
                {l.date && (
                  <span className="text-[10px] text-slate-400">{l.date}</span>
                )}
                {l.status && <Badge tone="info">{l.status}</Badge>}
                {l.promotion_candidate && <Badge tone="amber">promotion</Badge>}
              </div>
              <div className="text-slate-700 dark:text-slate-200">
                {truncate(l.trigger ?? l.problem ?? l.learning, 240)}
              </div>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

export default LessonsPanel;
