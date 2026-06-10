import { Card, CardHeader, CardTitle, CardBody } from './ui/Card';
import { Tabs } from './ui/Tabs';
import { Badge } from './ui/Badge';
import { SystemOfRecord } from './SystemOfRecord';
import { ContextMetrics } from './ContextMetrics';
import { LessonsPanel } from './LessonsPanel';
import type { Repo } from '../api/client';

interface Props {
  repo: Repo;
}

export function RepoPanel({ repo }: Props) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>
            <span
              aria-hidden="true"
              className="mr-2 inline-block h-2 w-2 rounded-full align-middle"
              style={{ backgroundColor: repo.color || '#94a3b8' }}
            />
            {repo.id}
          </CardTitle>
          {!repo.state_json_present && <Badge tone="warning">no state.json</Badge>}
        </div>
        <div className="mt-1 truncate font-mono text-[10px] text-slate-500" title={repo.project_dir}>
          {repo.project_dir}
        </div>
      </CardHeader>
      <CardBody className="flex-1 overflow-auto">
        <Tabs
          initial="system"
          tabs={[
            { id: 'system', label: 'System', content: <SystemOfRecord repoId={repo.id} /> },
            { id: 'context', label: 'Context', content: <ContextMetrics repoId={repo.id} /> },
            { id: 'lessons', label: 'Lessons', content: <LessonsPanel repoId={repo.id} /> },
          ]}
        />
      </CardBody>
    </Card>
  );
}

export default RepoPanel;
