export function Progress({
  value,
  max,
  className = '',
  tone = 'normal',
}: {
  value: number;
  max: number;
  className?: string;
  tone?: 'normal' | 'warning' | 'danger';
}) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const fillClass =
    tone === 'danger'
      ? 'bg-red-500'
      : tone === 'warning'
        ? 'bg-yellow-500'
        : 'bg-blue-500';
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      className={
        'relative h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800 ' + className
      }
    >
      <div
        className={'h-full ' + fillClass + ' transition-[width] duration-300 ease-out'}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
