FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

COPY backend/pyproject.toml backend/README.md ./backend/
COPY backend/src ./backend/src
COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/migrations ./backend/migrations

RUN pip install --no-cache-dir ./backend

COPY --from=frontend-build /frontend/dist ./frontend/dist

EXPOSE 8000

CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && uvicorn confluencr.main:app --host 0.0.0.0 --port 8000"]

