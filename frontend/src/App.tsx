import { FormEvent, useEffect, useState } from "react";

import {
  getHealth,
  getTransaction,
  submitTransaction,
  Transaction,
} from "./api";

const initialForm = {
  transaction_id: "txn_demo_001",
  source_account: "acc_user_789",
  destination_account: "acc_merchant_456",
  amount: 1500,
  currency: "INR",
};
const trackedTransactionStorageKey = "confluencr.tracked_transaction_id";

function getStoredTrackedTransactionId(): string {
  return window.localStorage.getItem(trackedTransactionStorageKey) ?? initialForm.transaction_id;
}

function App() {
  const [form, setForm] = useState(initialForm);
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [trackedId, setTrackedId] = useState(getStoredTrackedTransactionId);
  const [health, setHealth] = useState("Checking API...");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    getHealth()
      .then((result) => setHealth(result.status))
      .catch(() => setHealth("OFFLINE"));
  }, []);

  useEffect(() => {
    if (!trackedId) return;

    let cancelled = false;
    const refresh = async () => {
      try {
        const result = await getTransaction(trackedId);
        if (!cancelled && result) setTransaction(result);
      } catch (requestError) {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : "Request failed");
      }
    };

    void refresh();
    const intervalId = window.setInterval(refresh, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [trackedId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const accepted = await submitTransaction(form);
      setTrackedId(accepted.transaction_id);
      window.localStorage.setItem(trackedTransactionStorageKey, accepted.transaction_id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Request failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  function updateField(field: keyof typeof form, value: string | number) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">CONFLUENCR / TRANSACTION CONSOLE</p>
          <h1>Send a transaction webhook and watch it move.</h1>
          <p className="lede">
            A small full-stack surface over the assessment API. The backend acknowledges immediately,
            then processes the transaction in the background.
          </p>
        </div>
        <div className={`health-pill ${health === "HEALTHY" ? "healthy" : ""}`}>
          <span className="health-dot" />
          API {health}
        </div>
      </section>

      <section className="content-grid">
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
          {error && <p className="error-message">{error}</p>}
        </form>

        <section className="card status-card">
          <div className="card-heading">
            <div>
              <p className="section-label">LIVE STATUS</p>
              <h2>Transaction monitor</h2>
            </div>
            {transaction && <span className={`status-badge ${transaction.status.toLowerCase()}`}>{transaction.status}</span>}
          </div>

          {transaction ? (
            <div className="status-details">
              <div className="transaction-id">{transaction.transaction_id}</div>
              <div className="amount-display">
                {transaction.currency} {transaction.amount}
              </div>
              <dl>
                <div><dt>Created</dt><dd>{new Date(transaction.created_at).toLocaleTimeString()}</dd></div>
                <div><dt>Processed</dt><dd>{transaction.processed_at ? new Date(transaction.processed_at).toLocaleTimeString() : "Waiting for worker"}</dd></div>
              </dl>
              <p className="status-note">
                {transaction.status === "PROCESSED" ? "Processing completed successfully." : "Polling the API for completion..."}
              </p>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">↗</div>
              <p>Submit a webhook to start tracking a transaction.</p>
            </div>
          )}
        </section>
      </section>

      <section className="card assessment-card">
        <div className="card-heading">
          <div>
            <p className="section-label">ASSESSMENT FLOW</p>
            <h2>What this console verifies</h2>
          </div>
          <a className="docs-link" href="/docs" target="_blank" rel="noreferrer">Open API docs ↗</a>
        </div>
        <div className="assessment-steps">
          <div><span>1</span><strong>202 Accepted</strong><p>Webhook is acknowledged immediately.</p></div>
          <div><span>2</span><strong>Background processing</strong><p>Transaction remains visible while the worker runs.</p></div>
          <div><span>3</span><strong>Processed result</strong><p>Polling confirms the final persisted status.</p></div>
        </div>
      </section>
    </main>
  );
}

export default App;

