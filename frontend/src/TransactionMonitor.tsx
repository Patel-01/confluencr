import type { Transaction } from "./api";

export function TransactionMonitor({ transaction }: { transaction: Transaction | null }) {
  return (
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
            <div><dt>Processed</dt><dd>{transaction.processed_at ? new Date(transaction.processed_at).toLocaleTimeString() : "—"}</dd></div>
          </dl>
          <p className="status-note">
            {transaction.status === "PROCESSED"
              ? "Processing completed successfully."
              : transaction.status === "FAILED"
                ? "Processing failed. The transaction was not completed."
                : "Polling the API for completion..."}
          </p>
        </div>
      ) : (
        <div className="empty-state">
          <div className="empty-icon">↗</div>
          <p>Submit a webhook to start tracking a transaction.</p>
        </div>
      )}
    </section>
  );
}
