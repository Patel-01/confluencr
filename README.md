# Transaction Webhook Service

Clean, OOP-oriented FastAPI boilerplate for receiving transaction webhooks and processing them asynchronously.

## Architecture

The code is organized around dependency direction:

```text
presentation -> application -> domain
      |             |
      v             v
infrastructure  domain ports
```

- `domain` contains the transaction entity, state transitions, and repository contracts.
- `application` contains use cases and worker ports. It does not import FastAPI or SQLAlchemy.
- `infrastructure` contains SQLAlchemy persistence and the in-process worker implementation.
- `presentation` contains HTTP schemas, routes, dependency wiring, and application composition.

The in-process worker is intentionally replaceable. Transactions are persisted before acknowledgement, and `PROCESSING` rows are re-queued when the service starts, so a restart does not lose accepted work. A durable external queue/worker would still be the next scale-out step for high-volume production workloads.

The shared cloud database is Supabase PostgreSQL. For local development, SQLite remains the default. To use Supabase, set `DATABASE_URL` to the PostgreSQL connection string from the Supabase dashboard and keep that value server-side.

## Run locally

```powershell
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
uvicorn confluencr.main:app --reload
```

The API starts at `http://localhost:8000`. `GET /` is the assessment health endpoint, `/healthz` is the deployment health endpoint, and OpenAPI documentation is available at `/docs`.

## Run the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The React client starts at `http://localhost:5173`. Set `VITE_API_BASE_URL` if the API is running somewhere other than `http://localhost:8000`.

For production, the Docker image builds the React bundle and FastAPI serves it from the same origin when the browser requests HTML. API clients requesting JSON from `/` still receive the assessment health response. This keeps the deployed assessment app to one Render web service.

## API examples

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/webhooks/transactions `
  -ContentType "application/json" `
  -Body '{"transaction_id":"txn_abc123","source_account":"acc_user","destination_account":"acc_merchant","amount":1500,"currency":"INR"}'

Invoke-RestMethod http://localhost:8000/v1/transactions/txn_abc123
```

The webhook returns `202 Accepted` immediately. New transactions are initially `PROCESSING` and become `PROCESSED` after the configured delay.

## Test and quality checks

```powershell
pytest
ruff check .
mypy src
```

Tests override the processing delay to keep the suite fast and deterministic.

## Supabase database setup

The `cupcat` project owns the linked Supabase migration history. Its transaction migration must be applied before pointing this service at the cloud database:

```powershell
cd C:\Users\PANKAJ\cupcat
npx.cmd supabase db push --dry-run
npx.cmd supabase db push
```

Do not put a Supabase service-role key or database password in `VITE_` variables or commit them to Git.

## Render deployment

The public deployment uses one Docker web service. The image builds the React frontend, then FastAPI serves the frontend and API from the same origin:

- App: `https://confluencr-api.onrender.com`
- Health: `https://confluencr-api.onrender.com/healthz`
- API docs: `https://confluencr-api.onrender.com/docs`

Set the Render service variable `DATABASE_URL` to the Supabase PostgreSQL connection string before using the deployment for durable cloud storage. Without it, the service uses its local SQLite fallback, which is suitable only for a short-lived demo.

