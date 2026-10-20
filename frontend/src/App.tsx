import { useEffect, useState } from "react";

import {
  getHealth,
  getTransactions,
  submitTransaction,
} from "./api";
import type { TransactionPayload } from "./api";
import { TransactionForm } from "./TransactionForm";
import type { ApiEvidence } from "./TransactionForm";
import { TransactionMonitor } from "./TransactionMonitor";
import { useTransactionMonitor } from "./useTransactionMonitor";

const trackedTransactionStorageKey = "confluencr.tracked_transaction_id";

function getStoredTrackedTransactionId(): string {
  return window.localStorage.getItem(trackedTransactionStorageKey) ?? "";
}

function App() {
  const [trackedId, setTrackedId] = useState(getStoredTrackedTransactionId);
  const { transaction, error: monitorError } = useTransactionMonitor(trackedId);
  const [health, setHealth] = useState("Checking API...");
  const [submitError, setSubmitError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiEvidence, setApiEvidence] = useState<ApiEvidence | null>(null);

  useEffect(() => {
    getHealth()
      .then((result) => setHealth(result.status))
      .catch(() => setHealth("OFFLINE"));
  }, []);

  async function handleSubmit(form: TransactionPayload) {
    setSubmitError("");
    setIsSubmitting(true);

    try {
      const accepted = await submitTransaction(form);
      const storedTransactions = await getTransactions(accepted.data.transaction_id);
      const storedTransaction = storedTransactions[0];
      setTrackedId(accepted.data.transaction_id);
      window.localStorage.setItem(trackedTransactionStorageKey, accepted.data.transaction_id);
      setApiEvidence({
        method: "POST",
        path: "/v1/webhooks/transactions",
        statusCode: accepted.statusCode,
        body: {
          ...accepted.data,
          stored_records: storedTransactions.length,
          stored_amount: storedTransaction?.amount ?? null,
        },
      });
    } catch (requestError) {
      setSubmitError(requestError instanceof Error ? requestError.message : "Request failed");
    } finally {
      setIsSubmitting(false);
    }
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
        <TransactionForm
          onSubmit={handleSubmit}
          isSubmitting={isSubmitting}
          apiEvidence={apiEvidence}
          error={submitError}
          monitorError={monitorError}
        />
        <TransactionMonitor transaction={transaction} />
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

