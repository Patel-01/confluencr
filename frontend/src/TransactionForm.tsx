import { useState } from "react";
import type { FormEvent } from "react";

import type { TransactionPayload } from "./api";

const initialForm: TransactionPayload = {
  transaction_id: "txn_demo_001",
  source_account: "acc_user_789",
  destination_account: "acc_merchant_456",
  amount: 1500,
  currency: "INR",
};

export interface ApiEvidence {
  method: string;
  path: string;
  statusCode: number;
  body: Record<string, unknown>;
}

interface TransactionFormProps {
  onSubmit: (payload: TransactionPayload) => Promise<void>;
  isSubmitting: boolean;
  apiEvidence: ApiEvidence | null;
  error: string;
  monitorError: string;
}

export function TransactionForm({
  onSubmit,
  isSubmitting,
  apiEvidence,
  error,
  monitorError,
}: TransactionFormProps) {
  const [form, setForm] = useState(initialForm);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit(form);
  }

  function updateField(field: keyof TransactionPayload, value: string | number) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <form className="card form-card" onSubmit={handleSubmit}>
      <div className="card-heading">
        <div>
          <p className="section-label">WEBHOOK PAYLOAD</p>
          <h2>Submit transaction</h2>
        </div>
        <span className="method-badge">POST /v1/webhooks/transactions</span>
      </div>

      <label>
        Transaction ID
        <input value={form.transaction_id} onChange={(event) => updateField("transaction_id", event.target.value)} />
        <small className="field-hint">Use a new ID for a new transaction. Reusing an ID is intentionally idempotent.</small>
      </label>
      <div className="two-columns">
        <label>
          Source account
          <input value={form.source_account} onChange={(event) => updateField("source_account", event.target.value)} />
        </label>
        <label>
          Destination account
          <input value={form.destination_account} onChange={(event) => updateField("destination_account", event.target.value)} />
        </label>
      </div>
      <div className="two-columns">
        <label>
          Amount
          <input type="number" min="0.01" step="0.01" value={form.amount} onChange={(event) => updateField("amount", Number(event.target.value))} />
        </label>
        <label>
          Currency
          <input maxLength={3} value={form.currency} onChange={(event) => updateField("currency", event.target.value.toUpperCase())} />
        </label>
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Sending..." : "Send webhook"}
      </button>
      {apiEvidence && (
        <section className="api-evidence" aria-live="polite">
          <div className="api-evidence-heading">
            <div>
              <p className="section-label">API RESPONSE</p>
              <strong>{apiEvidence.method} {apiEvidence.path}</strong>
            </div>
            <span className="response-code">{apiEvidence.statusCode} ACCEPTED</span>
          </div>
          <pre>{JSON.stringify(apiEvidence.body, null, 2)}</pre>
        </section>
      )}
      {error && <p className="error-message">{error}</p>}
      {monitorError && <p className="error-message">{monitorError}</p>}
    </form>
  );
}
