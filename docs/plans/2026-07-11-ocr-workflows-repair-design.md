# OCR workflows repair design

## Goal

Repair OCR quota feedback, provider lifecycle management, upload requests, and the settings/upload workflows while keeping OCR configurations as replaceable service entry points.

## Provider lifecycle

An OCR provider configuration is operational state, not historical business data. At most one configuration is active. Activating one configuration automatically deactivates every other configuration. The UI presents a single `active` concept even though the existing database columns remain compatible with `enabled` and `is_default`.

Administrators can create, view, edit, test, activate, rotate credentials, and permanently delete configurations. Usage counters and quota alerts belong to the configuration and are deleted with it. Audit rows remain because their resource UUID is not a foreign key.

OCR jobs represent provider-independent recognition work. Creating a job does not bind it to a configuration. Whenever a worker starts an attempt, it resolves the currently active configuration, decrypts that configuration's credentials, applies its rate limit, and records provider, endpoint, action, version, and region on the job as an execution snapshot. Queued and retry-scheduled jobs therefore use whichever configuration is active when their next attempt actually starts.

The `provider_config_id` relationship is removed from OCR jobs. Provider snapshot columns become nullable until the first attempt starts. Deleting a configuration never mutates queued, retryable, completed, or failed jobs. If no configuration is active when an attempt starts, the job remains retryable with a clear `OCR_PROVIDER_NOT_CONFIGURED` error and can continue automatically after an administrator activates a service.

## Quota behavior

Quota input semantics remain `total` and `used`; remaining is always calculated as `max(total - used, 0)`. Validation rejects negative values and `used > total` when both values are present.

The global quota status represents the active provider only and includes its display name. Provider rows show total, used, and remaining directly. Existing same-level alert records refresh their snapshot values so warnings cannot retain stale totals or usage.

## Settings workflow

The settings page uses a focused provider list as the main surface. Add, view, edit, and delete confirmation use the project's existing native dialog pattern. Row actions use icons with tooltips where appropriate. Connection-test feedback is stored per provider row and never shares the create-form message state.

The create/edit dialog groups identity, connection, credentials, capacity, and warning thresholds. Secrets are never returned by the API; edit mode leaves credentials unchanged unless the administrator enters a replacement pair.

## Upload workflow

The shared API client must leave `Content-Type` unset for `FormData`, allowing the browser to generate a valid multipart boundary. Upload errors surface structured FastAPI validation detail when available.

The upload page becomes a three-stage workspace: choose files, confirm project/scene/OCR behavior, then upload and monitor progress. Settings appear inline only after files pass validation, reducing the number of simultaneous work panels. Quota status is compact supporting information and does not dominate the primary task.

## Other pages

This change performs a consistency audit across operational pages and applies only low-risk shared spacing, action, loading, empty, and error-state improvements. It does not redesign unrelated business workflows.

## Testing

Backend regression tests cover quota semantics and validation, alert refresh, single-active behavior, direct deletion, provider-independent job creation, execution-time provider selection, provider switching for queued/retry work, and historical snapshots. Frontend tests cover multipart headers, settings dialog/actions and row-scoped feedback, active-provider quota selection, and staged upload rendering. Existing backend, frontend, build, migration, and browser workflows remain the final verification gate.
