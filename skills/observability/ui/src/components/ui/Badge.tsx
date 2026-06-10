import type { HTMLAttributes, ReactNode } from 'react';

export type BadgeTone = 'default' | 'success' | 'info' | 'warning' | 'muted' | 'amber';

const TONE_CLASSES: Record<BadgeTone, string> = {
  default:
    'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:border-slate-700',
  success:
    'bg-green-100 text-green-800 border-green-200 dark:bg-green-900/40 dark:text-green-200 dark:border-green-800',
  info: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/40 dark:text-blue-200 dark:border-blue-800',
  warning:
    'bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-200 dark:border-yellow-800',
  muted:
    'bg-slate-50 text-slate-500 border-slate-200 dark:bg-slate-900 dark:text-slate-400 dark:border-slate-800',
  amber:
    'bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200 dark:border-amber-800',
};

export function Badge({
  tone = 'default',
  className = '',
  children,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone; children?: ReactNode }) {
  return (
    <span
      className={
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ' +
        TONE_CLASSES[tone] +
        ' ' +
        className
      }
      {...rest}
    >
      {children}
    </span>
  );
}

/** Map a story/phase status string to a Badge tone. */
export function statusTone(status: string): BadgeTone {
  switch (status) {
    case 'complete':
      return 'success';
    case 'planned':
    case 'in-progress':
      return 'info';
    case 'deferred':
    case 'draft':
      return 'warning';
    default:
      return 'muted';
  }
}
