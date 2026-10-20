# Transaction Webhook Service

Clean, OOP-oriented FastAPI boilerplate for receiving transaction webhooks and processing them asynchronously.

## Demo

[Watch the full-stack transaction demo](https://youtu.be/8D1t8_wqux8) to see a transaction submitted, acknowledged, processed in the background, and explored through the API documentation.

## Architecture

The repository keeps the two application halves visible at the top level:

```text
backend/    FastAPI service, Python package, and backend tests
frontend/   React transaction console
Dockerfile  Builds and serves both as one Render web service
```

Backend implementation lives in `backend/src/confluencr/` and tests live in `backend/tests/`.

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

The in-process worker is intentionally replaceable. Transactions are persisted before acknowledgement; database polling rediscovers due work and retries, including after restarts. Atomic claims with expiring, unique lease tokens prevent multiple service processes or stale workers from overwriting each other. This keeps accepted work recoverable without a separate broker, while a dedicated queue/worker remains a sensible scale-out step for higher-volume production workloads.

The deployed cloud database is Render PostgreSQL. For local development, SQLite remains the default. Alembic migrations manage schema changes; application startup does not mutate the schema. Supabase remains supported through the same `DATABASE_URL` setting if the service is moved back to the shared `cupcat` database.

The React client creates an anonymous UUID per browser profile and sends it as `X-Session-ID`. The API stores only session-level activity metadata (`client_sessions` and `session_activities`), not request payloads. `GET /v1/session/summary` returns the call count and recent API activity for that browser session, which keeps the transaction console useful across refreshes without requiring login.

## Run locally

```powershell
cd backend
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
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

Run frontend tests and the production build from `frontend/` with `npm test` and `npm run build`.

For production, the Docker image builds the React bundle and FastAPI serves it from the same origin when the browser requests HTML. API clients requesting JSON from `/` still receive the assessment health response. This keeps the deployed assessment app to one Render web service.

## API examples

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/v1/webhooks/transactions `
  -ContentType "application/json" `
  -Body '{"transaction_id":"txn_abc123","source_account":"acc_user","destination_account":"acc_merchant","amount":1500,"currency":"INR"}'

Invoke-RestMethod http://localhost:8000/v1/transactions/txn_abc123

Invoke-RestMethod http://localhost:8000/v1/session/summary `
  -Headers @{'X-Session-ID'='00000000-0000-0000-0000-000000000001'}
```

The webhook returns `202 Accepted` immediately. New transactions are initially `PROCESSING` and become `PROCESSED` after the configured delay.

## Test and quality checks

```powershell
cd backend
pytest
ruff check .
mypy src
```

Tests override the processing delay to keep the suite fast and deterministic.

## Optional Supabase database setup

The `cupcat` project owns the linked Supabase migration history. Its transaction migration must be applied before pointing this service at the cloud database:

```powershell
cd C:\Users\PANKAJ\cupcat
npx.cmd supabase db push --dry-run
npx.cmd supabase db push
```

The service's local environment template is `backend/.env.example`.

Do not put a Supabase service-role key or database password in `VITE_` variables or commit them to Git.

## Render deployment

The public deployment uses one Docker web service. The image builds the React frontend, then FastAPI serves the frontend and API from the same origin:

- App: `https://confluencr-api.onrender.com`
- Health: `https://confluencr-api.onrender.com/healthz`
- API docs: `https://confluencr-api.onrender.com/docs`

The Render service has `DATABASE_URL` configured with the internal Render PostgreSQL connection string. The current free Render database is scheduled to expire on November 18, 2026; upgrade or replace it before that date for continued persistence.

