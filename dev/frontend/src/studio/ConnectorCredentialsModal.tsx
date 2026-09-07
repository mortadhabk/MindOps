import { X } from "lucide-react";

import { SettingsView } from "../settings/SettingsView";

/** Identifiants des connecteurs externes (GitHub/SharePoint/Jira) — accessibles depuis le Studio,
 * pas depuis l'Admin générique : c'est ici, au moment de brancher une source, qu'on en a besoin,
 * jamais avant. Réutilise le même mécanisme de paramétrage chiffré (Epic 9) que le reste de
 * l'application, juste filtré à cette unique section (voir SettingsView `only`). */
export function ConnectorCredentialsModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="max-h-[85vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-white/10 bg-surface-900 p-5 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">Identifiants des connecteurs</h3>
            <p className="mt-0.5 text-xs text-slate-500">
              Chiffrés avant stockage — nécessaires une seule fois, partagés par toutes les
              instances d'un même type de connecteur.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 transition hover:text-slate-300"
            aria-label="Fermer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <SettingsView only={["connector_credentials"]} />
      </div>
    </div>
  );
}
