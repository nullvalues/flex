import { useMemo, useState } from 'react';
import { useSystem, type Phase, type Story, ApiError } from '../api/client';
import { Card, CardHeader, CardTitle, CardBody } from './ui/Card';
import { Badge, statusTone } from './ui/Badge';
import { Skeleton } from './ui/Skeleton';
import { Separator } from './ui/Separator';

interface Props {
  repoId: string;
}

function StoryRow({ story }: { story: Story }) {
  return (
    <li className="flex flex-col gap-0.5 border-l border-slate-200 pl-3 py-1 text-xs dark:border-slate-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-slate-500 dark:text-slate-400">{story.id}</span>
        <Badge tone={statusTone(story.status)}>{story.status || 'unknown'}</Badge>
        {story.flex_factor !== 1.0 && (
          <Badge tone="amber" title="Non-default flex_factor">
            flex×{story.flex_factor.toFixed(2)}
          </Badge>
        )}
        {story.story_class && story.story_class !== 'code' && (
          <Badge tone="muted">{story.story_class}</Badge>
        )}
      </div>
      <div className="text-slate-700 dark:text-slate-200">{story.title || '(untitled)'}</div>
    </li>
  );
}

function PhaseBlock({ phase, defaultOpen }: { phase: Phase; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const tone = statusTone(phase.status);

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-md bg-slate-100 px-2 py-1.5 text-left text-sm hover:bg-slate-200 dark:bg-slate-800/60 dark:hover:bg-slate-800"
      >
        <span className="flex items-center gap-2">
          <span
            aria-hidden="true"
            className={
              'inline-block w-3 text-xs text-slate-500 transition-transform ' +
              (open ? 'rotate-90' : '')
            }
          >
            ▶
          </span>
          <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
            phase {phase.phase_ref}
          </span>
          <span className="text-slate-800 dark:text-slate-100">{phase.title ?? '(untitled)'}</span>
        </span>
        <Badge tone={tone}>{phase.status}</Badge>
      </button>

      {open && (
        <div className="mt-2 pl-2">
          {phase.stories.length === 0 ? (
            <p className="text-xs text-slate-500">No stories listed.</p>
          ) : (
            <ul className="space-y-1">
              {phase.stories.map((s) => (
                <StoryRow key={s.id} story={s} />
              ))}
            </ul>
          )}
          {phase.deferred.length > 0 && (
            <>
              <Separator />
              <div className="text-[11px] text-slate-500">
                Deferred: {phase.deferred.join(', ')}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export function SystemOfRecord({ repoId }: Props) {
  const { data, isLoading, error } = useSystem(repoId);

  const phases = data?.phases ?? [];
  const defaultOpenIds = useMemo(() => {
    // Show last 5 expanded; rest collapsed
    const ids = phases.map((p) => p.phase_ref);
    return new Set(ids.slice(-5));
  }, [phases]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>System of Record</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="space-y-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-3/4" />
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
          <CardTitle>System of Record</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-red-600 dark:text-red-300">
            Error fetching system: HTTP {apiErr.status ?? '?'} — {apiErr.message}
          </p>
        </CardBody>
      </Card>
    );
  }

  if (phases.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>System of Record</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="text-xs text-slate-500">No phases found for this repo.</p>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>System of Record</CardTitle>
      </CardHeader>
      <CardBody>
        {phases.map((p) => (
          <PhaseBlock
            key={p.phase_ref}
            phase={p}
            defaultOpen={defaultOpenIds.has(p.phase_ref)}
          />
        ))}
      </CardBody>
    </Card>
  );
}

export default SystemOfRecord;
