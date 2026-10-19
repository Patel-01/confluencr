const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://localhost:8000" : "");
const sessionStorageKey = "confluencr.session_id";

function getSessionId(): string {
  const existing = window.localStorage.getItem(sessionStorageKey);
  if (existing) return existing;

  const sessionId = crypto.randomUUID();
  window.localStorage.setItem(sessionStorageKey, sessionId);
  return sessionId;
}

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
  const headers = new Headers(init?.headers);
  headers.set("Content-Type", "application/json");
  headers.set("X-Session-ID", getSessionId());
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
  });

  const responseSessionId = response.headers.get("X-Session-ID");
  if (responseSessionId) window.localStorage.setItem(sessionStorageKey, responseSessionId);

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getHealth(): Promise<{ status: string; current_time: string }> {
  return request("/healthz");
}

export interface SessionActivity {
  method: string;
  path: string;
  status_code: number;
  created_at: string;
}

export interface SessionSummary {
  session_id: string;
  total_api_calls: number;
  first_seen_at: string | null;
  last_seen_at: string | null;
  recent_activity: SessionActivity[];
}

export function getSessionSummary(): Promise<SessionSummary> {
  return request("/v1/session/summary");
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

