import type { ReactNode } from "react";
import clsx from "clsx";
import { RefreshCw } from "lucide-react";

export function EmptyState({ label }: { label: string }) {
  return <p className="py-8 text-center text-xs text-slate-500">{label}</p>;
}

export function RefreshButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Actualiser"
      className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/5 hover:text-slate-200"
    >
      <RefreshCw className="h-3.5 w-3.5" />
    </button>
  );
}

interface IconButtonProps {
  label: string;
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  variant: "approve" | "reject";
}

export function IconButton({ label, icon, onClick, disabled, variant }: IconButtonProps) {
  return (
    <button
      type="button"
      title={label}
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        "flex h-6 w-6 items-center justify-center rounded-full transition disabled:opacity-40",
        variant === "approve"
          ? "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
          : "bg-rose-500/20 text-rose-300 hover:bg-rose-500/30",
      )}
    >
      {icon}
    </button>
  );
}
