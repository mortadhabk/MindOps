import type { SettingsSection } from "../lib/api";
import { DynamicSchemaField } from "./DynamicSchemaField";

interface VendorInfo {
  display_name: string;
  default_base_url: string | null;
  known_models: string[];
}

interface AgentSettingsFieldsProps {
  section: SettingsSection;
  values: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

/** Section "agent" : spécialisée plutôt que rendue par la boucle générique de champs — le choix
 * du fournisseur détermine dynamiquement l'URL par défaut et les modèles suggérés, un
 * comportement inter-champs que le mapping JSON Schema générique ne couvre pas (même logique que
 * le cas particulier "document" dans le Studio, Epic 8). */
export function AgentSettingsFields({ section, values, onChange }: AgentSettingsFieldsProps) {
  const vendors = (section.read_only.vendors ?? {}) as Record<string, VendorInfo>;
  const vendorEntries = Object.entries(vendors);
  const currentVendorKey = String(values.llm_vendor ?? "ollama");
  const currentVendor = vendors[currentVendorKey];
  const apiKeyProperty = section.config_schema.properties.api_key;
  const required = new Set(section.config_schema.required ?? []);

  const handleVendorChange = (vendorKey: string) => {
    onChange("llm_vendor", vendorKey);
    const vendor = vendors[vendorKey];
    if (!vendor) return;
    onChange("base_url", vendor.default_base_url ?? "");
    if (!vendor.known_models.includes(String(values.llm_model ?? ""))) {
      onChange("llm_model", vendor.known_models[0] ?? "");
    }
  };

  return (
    <>
      <div>
        <label className="mb-1 block text-[11px] font-medium text-slate-400">
          Fournisseur<span className="text-rose-400"> *</span>
        </label>
        <select
          value={currentVendorKey}
          onChange={(event) => handleVendorChange(event.target.value)}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
        >
          {vendorEntries.map(([key, vendor]) => (
            <option key={key} value={key} className="bg-surface-900">
              {vendor.display_name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-[11px] font-medium text-slate-400">
          Modèle<span className="text-rose-400"> *</span>
        </label>
        <input
          list="llm-model-options"
          value={String(values.llm_model ?? "")}
          onChange={(event) => onChange("llm_model", event.target.value)}
          placeholder="Choisir dans la liste ou saisir un modèle…"
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
        />
        <datalist id="llm-model-options">
          {(currentVendor?.known_models ?? []).map((model) => (
            <option key={model} value={model} />
          ))}
        </datalist>
        <p className="mt-1 text-[10px] text-slate-600">
          Liste suggérée pour {currentVendor?.display_name ?? "ce fournisseur"} — un modèle plus
          récent, absent de la liste, peut être saisi librement.
        </p>
      </div>

      <div>
        <label className="mb-1 block text-[11px] font-medium text-slate-400">
          URL du serveur
        </label>
        <input
          value={String(values.base_url ?? "")}
          onChange={(event) => onChange("base_url", event.target.value)}
          placeholder={currentVendor?.default_base_url ?? "http://localhost:11434"}
          className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-100 focus:border-indigo-400/50 focus:outline-none focus:ring-2 focus:ring-indigo-400/20"
        />
        <p className="mt-1 text-[10px] text-slate-600">
          Préremplie selon le fournisseur, modifiable (proxy, région différente, ...).
        </p>
      </div>

      {apiKeyProperty && (
        <DynamicSchemaField
          name="api_key"
          property={apiKeyProperty}
          required={required.has("api_key")}
          value={values.api_key}
          onChange={(value) => onChange("api_key", value)}
          hasStoredSecret={Boolean(section.current_values.api_key)}
        />
      )}
    </>
  );
}
