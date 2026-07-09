# Invoice OCR Operations Runbook

## Release Checklist

- Build the release image for `linux/amd64` with an immutable tag.
- Confirm the image user is `invoice`, not `root`.
- Generate and review the CI SBOM artifact.
- Review CI vulnerability scan results before promoting the image.
- Confirm `.env` contains only infrastructure settings and app encryption keys.
- Confirm Tencent Cloud `SecretId` and `SecretKey` are absent from `.env`, Compose files, shell history, and CI logs.
- Run database migrations with `docker compose run --rm app migrate`.
- Create the first administrator with `docker compose exec app invoice-app create-admin --email ... --password ...`.
- Configure OCR provider credentials from the admin settings UI.
- Test `/healthz` and `/readyz` before opening traffic.

## Standard Commands

```bash
docker buildx build --platform linux/amd64 -t invoice-ocr-app:0.1.0 .
docker inspect invoice-ocr-app:0.1.0 --format '{{.Config.User}}'
docker compose run --rm app migrate
docker compose up -d
docker compose ps
```

## Health Checks

- `/healthz` confirms the API process is running.
- `/readyz` confirms database and Redis dependencies are reachable.
- OCR provider connectivity is not part of readiness; test it manually from the admin settings page.

## Audit Logs

The application writes audit records for login, upload, OCR completion, invoice correction, export creation, OCR provider changes, credential rotation, quota calibration, and quota alert acknowledgement.

Audit metadata is redacted before persistence. Do not use audit logs for storing plaintext credentials, uploaded file contents, or OCR raw payloads.

## Incident Notes

- For failed OCR jobs, use the job `request_id` and provider error code visible to admins.
- For queue delays, check Redis health and Celery worker logs.
- For database errors, check `/readyz`, PostgreSQL logs, and recent migrations.
- For quota warnings, review active quota alerts and provider usage counters before raising QPS.

## Backup And Restore

- Back up PostgreSQL data and the `app_uploads` and `app_exports` volumes together.
- Restore database and file volumes as one point-in-time set to keep invoice records aligned with stored files.
- After restore, run `/readyz`, list recent invoices, and download a known export before resuming normal operation.
