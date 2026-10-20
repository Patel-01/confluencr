import { useEffect, useState } from "react";

import { getTransaction } from "./api";
import type { Transaction } from "./api";

export function useTransactionMonitor(trackedId: string): {
  transaction: Transaction | null;
  error: string;
} {
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!trackedId) {
      setTransaction(null);
      setError("");
      return;
    }

    let cancelled = false;
    let timeoutId: number | undefined;
    const refresh = async () => {
      try {
        const result = await getTransaction(trackedId);
        if (cancelled) return;
        setError("");
        setTransaction(result);
        if (result?.status === "PROCESSING") {
          timeoutId = window.setTimeout(() => void refresh(), 1000);
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "Request failed");
        }
      }
    };

    void refresh();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [trackedId]);

  return { transaction, error };
}
