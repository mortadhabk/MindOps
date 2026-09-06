import clsx from "clsx";
import { RotateCcw, Zap } from "lucide-react";
import { useEffect, useState } from "react";

import type { SettingsSection } from "../lib/api";
import { Panel } from "../components/Panel";
import { DynamicSchemaField } from "./DynamicSchemaField";

interface SettingsSectionCardProps {
  section: SettingsSection;
  onSave: (key: string, value: Record<string, unknown>) => Promise<void>;
  onReset: (key: string) => Promise<void>;
}

export function SettingsSectionCard({ section, onSave, onReset }: SettingsSectionCardProps) {
  const [values, setValues] = useState<Record<string, unknown>>(section.current_values);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Si le serveur renvoie une valeur différente (ex. reset déclenché ailleurs), on resynchronise
  // le formulaire — mais jamais pendant que l'utilisateur est en train de le remplir sans avoir
  // encore sauvegardé, pour ne pas écraser sa saisie en cours.
  useEffect(() => {
    if (!saving && !resetting) setValues(section.current_values);
  }, [section.current_values, saving, resetting]);

  const fields = Object.entries(section.config_schema.properties);
  const required = new Set(section.config_schema.required ?? []);
  const readOnlyEntries = Object.entries(section.read_only);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(section.key, values);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    setError(null);
    try {
      await onReset(section.key);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setResetting(false);
    }
  };

  return (
    <Panel
      title={section.display_name}
      actions={<EffectBadge effect={section.effect} hasOverride={section.has_override} />}
    >
      <div className="space-y-3 p-4">
        <p className="text-xs text-slate-500">{section.description}</p>

        {fields.map(([key, property]) => (
          <DynamicSchemaField
            key={key}
            name={key}
            property={property}
            required={required.has(key)}
            value={values[key]}
            onChange={(value) => setValues((prev) => ({ ...prev, [key]: value }))}
          />
        ))}

        {readOnlyEntries.length > 0 && (
          <div className="space-y-1 border-t border-white/10 pt-2">
            {readOnlyEntries.map(([key, value]) => (
              <div key={key} className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500">{key}</span>
                <span className="font-mono text-slate-400">{String(value)}</span>
              </div>
            ))}
            <p className="text-[10px] text-slate-600">Lecture seule — redéploiement requis pour changer.</p>
          </div>
        )}

        {error && <p className="text-xs text-rose-400">{error}</p>}

        <div className="flex items-center justify-between pt-1">
          <button
            type="button"
            onClick={handleReset}
            disabled={!section.has_override || resetting}
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium text-slate-400 transition hover:bg-white/5 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <RotateCcw className="h-3 w-3" />
            Réinitialiser
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-gradient-to-br from-indigo-500 to-sky-400 px-3.5 py-1.5 text-xs font-medium text-white transition disabled:opacity-50"
          >
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </Panel>
  );
}

function EffectBadge({ effect, hasOverride }: { effect: "immediate" | "deferred"; hasOverride: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      {hasOverride && (
        <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-medium text-indigo-200">
          personnalisé
        </span>
      )}
      <span
        className={clsx(
          "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
          effect === "immediate"
            ? "bg-emerald-500/15 text-emerald-300"
            : "bg-amber-500/15 text-amber-300",
        )}
        title={
          effect === "immediate"
            ? "S'applique dès la sauvegarde"
            : "S'applique à la prochaine requête concernée"
        }
      >
        <Zap className="h-2.5 w-2.5" />
        {effect === "immediate" ? "immédiat" : "différé"}
      </span>
    </div>
  );
}
