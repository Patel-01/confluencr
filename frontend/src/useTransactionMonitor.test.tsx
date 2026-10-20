// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getTransaction } from "./api";
import type { Transaction } from "./api";
import { useTransactionMonitor } from "./useTransactionMonitor";

vi.mock("./api", () => ({ getTransaction: vi.fn() }));

const processingTransaction: Transaction = {
  transaction_id: "txn_test",
  source_account: "source",
  destination_account: "destination",
  amount: "1.00",
  currency: "INR",
  status: "PROCESSING",
  created_at: "2026-01-01T00:00:00Z",
  processed_at: null,
};

afterEach(() => {
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("useTransactionMonitor", () => {
  it.each(["PROCESSED", "FAILED"] as const)(
    "stops polling when status becomes %s",
    async (status) => {
      vi.useFakeTimers();
      vi.mocked(getTransaction)
        .mockResolvedValueOnce(processingTransaction)
        .mockResolvedValueOnce({ ...processingTransaction, status });

      const { result } = renderHook(() => useTransactionMonitor("txn_test"));
      await act(async () => {});
      expect(getTransaction).toHaveBeenCalledTimes(1);
      expect(result.current.transaction?.status).toBe("PROCESSING");

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(getTransaction).toHaveBeenCalledTimes(2);
      expect(result.current.transaction?.status).toBe(status);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(getTransaction).toHaveBeenCalledTimes(2);
    },
  );

  it("does not poll when no transaction is selected", async () => {
    renderHook(() => useTransactionMonitor(""));
    await act(async () => {});

    expect(getTransaction).not.toHaveBeenCalled();
  });

  it("stops polling after an API lookup fails", async () => {
    vi.useFakeTimers();
    vi.mocked(getTransaction).mockRejectedValueOnce(new Error("not found"));

    const { result } = renderHook(() => useTransactionMonitor("stale-id"));
    await act(async () => {});
    expect(result.current.error).toBe("not found");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(getTransaction).toHaveBeenCalledTimes(1);
  });
});
