# Auto Migration Startup Design

## Goal

Make NAS and first-time Docker deployments product-like: users should be able to start the Compose project and open the browser without running a separate database migration command.

## Current problem

The frontend asks `/api/v1/auth/bootstrap-status` before showing the first-administrator form. That endpoint reads `system_state`. On a fresh PostgreSQL volume, the table does not exist until Alembic migrations run, so the API returns a database error and the page shows a generic connection failure.

## Design

Move the normal migration step into the container startup path for the `web` command:

1. The `web` command runs `alembic -c /app/alembic.ini upgrade head`.
2. If the database is already at head, Alembic is a no-op because it records applied revisions in `alembic_version`.
3. After migration succeeds, the container starts Uvicorn.
4. The existing `migrate` command remains available for advanced operators and troubleshooting.
5. An `AUTO_MIGRATE=false` escape hatch disables startup migrations for deployments that want a separate migration job.

## Data safety

This does not recreate PostgreSQL or delete Docker volumes. Existing data remains in the `postgres_data` volume. Alembic upgrades apply only unapplied migration revisions. Data loss would require destructive migrations, deleting volumes, or running `docker compose down -v`; this change does none of those.

## Documentation impact

First-time and upgrade commands should become:

```bash
docker compose pull
docker compose up -d
docker compose ps
```

Manual `docker compose run --rm app migrate` should be documented as an optional recovery/advanced command, not the default path.
