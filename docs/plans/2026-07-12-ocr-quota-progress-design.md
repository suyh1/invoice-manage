# OCR Quota Progress Design

## Goal

Replace the passive OCR quota reminder in the application sidebar and upload page with a shared quota progress indicator. The indicator shows used quota against total quota and changes its fill color when the configured warning threshold is reached.

## Data Contract

Add an authenticated OCR quota status endpoint separate from the existing administrative alert endpoint. It returns only the current enabled default provider's quota presentation data:

- `quota_total`
- `quota_used`
- `used_percent`
- `level`

All authenticated roles may read this status because the sidebar and upload page are shared application surfaces. Provider credentials and configuration details remain restricted to administrators.

When there is no enabled default provider or its quota values are incomplete, the endpoint returns null quota values and a `none` level rather than an error.

## Interface

`OcrQuotaStatus` remains the shared frontend component used by the sidebar and upload page.

The component renders:

- a hollow progress track with a black border;
- a fill whose width is the clamped `quota_used / quota_total` percentage;
- `quota_used/quota_total` to the right of the track;
- black fill while below the configured threshold;
- red fill at warning or critical level.

Loading, unavailable, and unconfigured states keep the hollow track at zero fill and display `--/--`. The old reminder sentence and normal/warning status copy are removed. The progress element exposes accessible progressbar semantics when numeric quota data is available.

## Threshold Behavior

The backend remains the source of truth for threshold evaluation. Its existing quota rules mark the status as warning when either the configured used percentage is reached or the configured remaining quota boundary is reached. Exhausted quota remains critical. Both warning and critical states use the red fill requested for threshold-reaching states.

## Testing

Backend tests cover normal quota snapshots, threshold-reaching snapshots, access for a non-admin authenticated user, and the unconfigured state. Frontend tests cover numeric rendering, percentage clamping, red threshold styling, and the `--/--` fallback. Existing test suites, type checking, and production build are run after implementation.
