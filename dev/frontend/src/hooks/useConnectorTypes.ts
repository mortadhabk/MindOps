import { useEffect, useState } from "react";

import { type ConnectorType, fetchConnectorTypes } from "../lib/api";

export function useConnectorTypes() {
  const [types, setTypes] = useState<ConnectorType[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchConnectorTypes()
      .then(setTypes)
      .finally(() => setLoading(false));
  }, []);

  return { types, loading };
}
