import { useCallback, useEffect, useState } from "react";

import {
  fetchSettingsSections,
  resetSettingsSection,
  type SettingsSection,
  updateSettingsSection,
} from "../lib/api";

export function useSettingsSections() {
  const [sections, setSections] = useState<SettingsSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchSettingsSections()
      .then(setSections)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  const update = useCallback(async (key: string, value: Record<string, unknown>) => {
    const updated = await updateSettingsSection(key, value);
    setSections((prev) => prev.map((s) => (s.key === key ? updated : s)));
  }, []);

  const reset = useCallback(async (key: string) => {
    const updated = await resetSettingsSection(key);
    setSections((prev) => prev.map((s) => (s.key === key ? updated : s)));
  }, []);

  return { sections, loading, error, refresh, update, reset };
}
