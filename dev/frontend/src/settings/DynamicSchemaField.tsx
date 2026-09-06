import { Trash2 } from "lucide-react";

import type { JsonSchemaProperty } from "../lib/api";

interface DynamicSchemaFieldProps {
  name: string;
  property: JsonSchemaProperty & { pattern?: string; minimum?: number; maximum?: number };
  required: boolean;
  value: unknown;
  onChange: (value: unknown) => void;
}

/** Rend un champ depuis une propriété de JSON Schema — même esprit que le mapping fait main du
 * Studio (Epic 8) : pas de librairie de formulaire générique, juste assez de cas pour couvrir
 * les schémas de paramétrage réels (string, éventuellement à choix fermé, nombre, objet clé/valeur). */
export function DynamicSchemaField({ name, property, required, value, onChange }: DynamicSchemaFieldProps) {
  const label = property.title ?? name;
  const options = extractEnumFromPattern(property.pattern);

  return (
    <div>
      <label className="mb-1 block text-[11px] font-medium text-slate-400">
        {label}
        {required && <span className="text-rose-400"> *</span>}
      </label>
      {property.type === "object" ? (
        <KeyValueEditor value={(value as Record<string, string>) ?? {}} onChange={onChange} />
      ) : options ? (
        <select
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
        >
          {options.map((option) => (
            <option key={option} value={option} className="bg-surface-900">
              {option}
            </option>
          ))}
        </select>
      ) : property.type === "integer" || property.type === "number" ? (
        <input
          type="number"
          value={String(value ?? "")}
          min={property.minimum}
          max={property.maximum}
          step={property.type === "integer" ? 1 : "any"}
          onChange={(event) => onChange(Number(event.target.value))}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
        />
      ) : (
        <input
          value={String(value ?? "")}
          onChange={(event) => onChange(event.target.value)}
          placeholder={property.examples?.[0] != null ? String(property.examples[0]) : undefined}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
        />
      )}
      {property.description && <p className="mt-1 text-[10px] text-slate-600">{property.description}</p>}
    </div>
  );
}

function extractEnumFromPattern(pattern?: string): string[] | null {
  // Reconnaît les regex "^(A|B|C)$" générées par des Literal/enum Pydantic — évite de saisir à la
  // main une valeur qui n'existe pas (ex. log_level).
  const match = pattern?.match(/^\^\(([\w|]+)\)\$$/);
  return match ? match[1].split("|") : null;
}

function KeyValueEditor({
  value,
  onChange,
}: {
  value: Record<string, string>;
  onChange: (value: Record<string, string>) => void;
}) {
  const entries = Object.entries(value);

  const updateEntry = (index: number, key: string, entryValue: string) => {
    const next = [...entries];
    next[index] = [key, entryValue];
    onChange(Object.fromEntries(next));
  };

  const removeEntry = (index: number) => {
    onChange(Object.fromEntries(entries.filter((_, i) => i !== index)));
  };

  return (
    <div className="space-y-1.5 rounded-lg border border-white/10 bg-white/[0.02] p-2">
      {entries.map(([key, entryValue], index) => (
        <div key={index} className="flex gap-1.5">
          <input
            value={key}
            onChange={(event) => updateEntry(index, event.target.value, entryValue)}
            placeholder="type d'action"
            className="w-1/2 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs text-slate-100 focus:border-indigo-400/50 focus:outline-none"
          />
          <input
            value={entryValue}
            onChange={(event) => updateEntry(index, key, event.target.value)}
            placeholder="suggest_only | require_validation | auto_execute"
            className="flex-1 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs text-slate-100 focus:border-indigo-400/50 focus:outline-none"
          />
          <button
            type="button"
            onClick={() => removeEntry(index)}
            className="rounded-md p-1 text-slate-500 transition hover:bg-rose-500/10 hover:text-rose-300"
            aria-label="Supprimer cette entrée"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange({ ...value, "": "" })}
        className="text-[11px] font-medium text-indigo-300 hover:text-indigo-200"
      >
        + Ajouter une entrée
      </button>
    </div>
  );
}
