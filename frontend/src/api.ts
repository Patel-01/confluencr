const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://localhost:8000" : "");

export type TransactionStatus = "PROCESSING" | "PROCESSED";

export interface Transaction {
  transaction_id: string;
  source_account: string;
  destination_account: string;
  amount: string;
  currency: string;
  status: TransactionStatus;
  created_at: string;
  processed_at: string | null;
}

export interface TransactionPayload {
  transaction_id: string;
  source_account: string;
  destination_account: string;
  amount: number;
  currency: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getHealth(): Promise<{ status: string; current_time: string }> {
  return request("/healthz");
}

export function submitTransaction(payload: TransactionPayload): Promise<{
  status: string;
  transaction_id: string;
}> {
  return request("/v1/webhooks/transactions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTransaction(transactionId: string): Promise<Transaction | null> {
  const transactions = await request<Transaction[]>(
    `/v1/transactions/${encodeURIComponent(transactionId)}`,
  );
  return transactions[0] ?? null;
}

