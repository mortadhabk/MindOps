import { type FormEvent, useState } from "react";
import { X } from "lucide-react";

import type { ConnectorType } from "../lib/api";

interface ConnectorConfigModalProps {
  connectorType: ConnectorType;
  onCancel: () => void;
  onSubmit: (displayName: string, config: Record<string, string>) => Promise<void>;
}

/** Formulaire généré depuis le JSON Schema de `Connector.config_schema` (Epic 8) : un mapping
 * fait main plutôt qu'une librairie de rendu de formulaire — les schémas visés ici (2-3 champs
 * texte par connecteur) ne justifient pas la dépendance et le poids d'une lib générique. */
export function ConnectorConfigModal({
  connectorType,
  onCancel,
  onSubmit,
}: ConnectorConfigModalProps) {
  const [displayName, setDisplayName] = useState(connectorType.display_name);
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const [key, prop] of Object.entries(connectorType.config_schema.properties)) {
      if (typeof prop.default === "string") initial[key] = prop.default;
    }
    return initial;
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const required = new Set(connectorType.config_schema.required ?? []);
  const fields = Object.entries(connectorType.config_schema.properties);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(displayName, values);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl border border-white/10 bg-surface-900 p-5 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-100">
            Configurer « {connectorType.display_name} »
          </h3>
          <button
            type="button"
            onClick={onCancel}
            className="text-slate-500 transition hover:text-slate-300"
            aria-label="Fermer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-1 text-xs text-slate-500">{connectorType.description}</p>

        <div className="mt-4 max-h-[50vh] space-y-3 overflow-y-auto pr-1">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-slate-400">
              Nom de cette source
            </label>
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              required
              className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
            />
          </div>
          {fields.map(([key, prop]) => (
            <div key={key}>
              <label className="mb-1 block text-[11px] font-medium text-slate-400">
                {prop.title ?? key}
                {required.has(key) && <span className="text-rose-400"> *</span>}
              </label>
              <input
                value={values[key] ?? ""}
                onChange={(event) =>
                  setValues((prev) => ({ ...prev, [key]: event.target.value }))
                }
                required={required.has(key)}
                placeholder={
                  prop.examples?.[0] != null ? String(prop.examples[0]) : undefined
                }
                className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
              />
              {prop.description && (
                <p className="mt-1 text-[10px] text-slate-600">{prop.description}</p>
              )}
            </div>
          ))}
          {fields.length === 0 && (
            <p className="text-[11px] text-slate-600">Ce connecteur ne nécessite aucun paramètre.</p>
          )}
        </div>

        {error && <p className="mt-3 text-xs text-rose-400">{error}</p>}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg px-3 py-1.5 text-xs text-slate-400 transition hover:text-slate-200"
          >
            Annuler
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-gradient-to-br from-indigo-500 to-sky-400 px-3.5 py-1.5 text-xs font-medium text-white transition disabled:opacity-50"
          >
            {submitting ? "Ajout…" : "Ajouter au canvas"}
          </button>
        </div>
      </form>
    </div>
  );
}
