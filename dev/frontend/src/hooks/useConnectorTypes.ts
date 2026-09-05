import { useCallback, useEffect, useState } from "react";

import { type ConnectorType, fetchConnectorTypes } from "../lib/api";

export function useConnectorTypes() {
  const [types, setTypes] = useState<ConnectorType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchConnectorTypes()
      .then(setTypes)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  return { types, loading, error, refresh };
}
