export function Separator({ className = '' }: { className?: string }) {
  return (
    <div
      role="separator"
      aria-orientation="horizontal"
      className={'my-2 h-px w-full bg-slate-200 dark:bg-slate-800 ' + className}
    />
  );
}
