import type { ReactNode } from "react";
import clsx from "clsx";

interface PanelProps {
  title: string;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, icon, actions, children, className }: PanelProps) {
  return (
    <section
      className={clsx(
        "flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]",
        "shadow-xl shadow-black/20 backdrop-blur-xl",
        className,
      )}
    >
      <header className="flex items-center justify-between gap-3 border-b border-white/10 px-5 py-3.5">
        <div className="flex items-center gap-2 text-sm font-semibold tracking-wide text-slate-100">
          {icon}
          {title}
        </div>
        {actions}
      </header>
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}
