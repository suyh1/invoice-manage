FROM node:24.13.0-bookworm-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_PORT=8080

WORKDIR /app

RUN pip install --no-cache-dir \
    "cryptography==46.0.3" \
    "fastapi==0.116.0" \
    "uvicorn[standard]==0.35.0" \
    "pydantic-settings==2.10.1" \
  && addgroup --system invoice \
  && adduser --system --ingroup invoice invoice

COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./app/static

RUN mkdir -p /data/uploads /data/exports /data/tmp \
  && chown -R invoice:invoice /app /data

USER invoice
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
