import { useEffect, useState } from "react";

import { getHealth } from "./api";

export type ApiHealth = "CHECKING" | "HEALTHY" | "RETRYING";

const healthCheckTimeoutMs = 5_000;
const healthRetryIntervalMs = 10_000;

export function useApiHealth(): ApiHealth {
  const [health, setHealth] = useState<ApiHealth>("CHECKING");

  useEffect(() => {
    let isActive = true;
    let retryTimer: number | undefined;
    let timeoutTimer: number | undefined;
    let controller: AbortController | undefined;

    async function checkHealth() {
      controller = new AbortController();
      timeoutTimer = window.setTimeout(
        () => controller?.abort(),
        healthCheckTimeoutMs,
      );

      try {
        const result = await getHealth(controller.signal);
        if (isActive) {
          setHealth(result.status === "HEALTHY" ? "HEALTHY" : "RETRYING");
        }
      } catch {
        if (isActive) setHealth("RETRYING");
      } finally {
        if (timeoutTimer !== undefined) window.clearTimeout(timeoutTimer);
        if (isActive) {
          retryTimer = window.setTimeout(checkHealth, healthRetryIntervalMs);
        }
      }
    }

    void checkHealth();

    return () => {
      isActive = false;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      if (timeoutTimer !== undefined) window.clearTimeout(timeoutTimer);
      controller?.abort();
    };
  }, []);

  return health;
}
