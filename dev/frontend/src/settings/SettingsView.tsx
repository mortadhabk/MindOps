import { RefreshCw } from "lucide-react";

import { useSettingsSections } from "../hooks/useSettingsSections";
import { SettingsSectionCard } from "./SettingsSectionCard";

export function SettingsView() {
  const { sections, loading, error, refresh, update, reset } = useSettingsSections();

  if (loading && sections.length === 0) {
    return <p className="px-1 py-8 text-center text-sm text-slate-500">Chargement des paramètres…</p>;
  }

  if (error && sections.length === 0) {
    return (
      <div className="mx-auto max-w-md rounded-xl border border-rose-500/20 bg-rose-500/[0.06] p-4 text-center text-sm text-rose-300">
        <p>Impossible de charger les paramètres : {error}</p>
        <button
          type="button"
          onClick={refresh}
          className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10"
        >
          <RefreshCw className="h-3 w-3" />
          Réessayer
        </button>
      </div>
    );
  }

  return (
    <div className="grid gap-5 sm:grid-cols-2">
      {sections.map((section) => (
        <SettingsSectionCard key={section.key} section={section} onSave={update} onReset={reset} />
      ))}
    </div>
  );
}
