import type { HTMLAttributes, ReactNode } from 'react';

export function Card({
  className = '',
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children?: ReactNode }) {
  return (
    <div
      className={
        'rounded-lg border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 ' +
        className
      }
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  className = '',
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children?: ReactNode }) {
  return (
    <div className={'border-b border-slate-200 px-3 py-2 dark:border-slate-800 ' + className} {...rest}>
      {children}
    </div>
  );
}

export function CardTitle({
  className = '',
  children,
  ...rest
}: HTMLAttributes<HTMLHeadingElement> & { children?: ReactNode }) {
  return (
    <h3 className={'text-sm font-semibold tracking-tight ' + className} {...rest}>
      {children}
    </h3>
  );
}

export function CardBody({
  className = '',
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children?: ReactNode }) {
  return (
    <div className={'p-3 ' + className} {...rest}>
      {children}
    </div>
  );
}
