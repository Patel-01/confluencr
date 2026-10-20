// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getHealth } from "./api";
import { useApiHealth } from "./useApiHealth";

vi.mock("./api", () => ({ getHealth: vi.fn() }));

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("useApiHealth", () => {
  it("retries a failed check and returns to healthy when the API recovers", async () => {
    vi.useFakeTimers();
    vi.mocked(getHealth)
      .mockRejectedValueOnce(new Error("temporary network error"))
      .mockResolvedValue({ status: "HEALTHY", current_time: "2026-10-20T00:00:00Z" });

    const { result } = renderHook(() => useApiHealth());
    await act(async () => {});

    expect(result.current).toBe("RETRYING");
    expect(getHealth).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(result.current).toBe("HEALTHY");
    expect(getHealth).toHaveBeenCalledTimes(2);
    expect(vi.mocked(getHealth).mock.calls[0][0]).toBeInstanceOf(AbortSignal);
  });

  it("aborts an in-flight health check on unmount", async () => {
    vi.useFakeTimers();
    vi.mocked(getHealth).mockImplementation((_signal) => new Promise(() => {}));

    const { unmount } = renderHook(() => useApiHealth());
    await act(async () => {});
    const signal = vi.mocked(getHealth).mock.calls[0][0];

    unmount();

    expect(signal?.aborted).toBe(true);
  });
});
