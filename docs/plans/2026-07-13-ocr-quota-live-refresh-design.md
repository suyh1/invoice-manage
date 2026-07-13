# OCR Quota Live Refresh Design

## Goal

Update every visible OCR quota indicator automatically after an OCR provider call returns, without requiring a page refresh.

## Billing Semantics

An actual provider call consumes quota whether recognition succeeds or fails. `record_provider_call` must therefore increment `free_quota_used` and `estimated_billable_calls` for both successful and failed provider responses. Success and failure counters remain mutually exclusive.

Local rate limiting and other paths that return before `_recognize` calls the provider do not record usage and do not consume quota.

## Frontend Refresh Signal

Add a small browser-level OCR quota refresh module with a stable event name. It exposes functions to publish a refresh signal and subscribe to it.

`OcrQuotaStatus` keeps its existing initial request and additionally reloads quota when:

- the shared refresh event is published;
- the document becomes visible again;
- the browser window regains focus.

Every mounted quota component receives the same event, so the sidebar and the current page indicator update together.

## OCR Result Observation

The upload page already polls OCR jobs. It publishes the quota refresh signal when polling observes a provider-result status:

- `completed`;
- `failed_final` or `failed`;
- `retry_scheduled`.

Notifications are deduplicated by `attempt_count`, so a retry-scheduled job refreshes once per completed provider attempt instead of once per polling request.

Invoice detail and review queue retries currently enqueue work without observing the result. After a retry is accepted, they start a reusable background watcher that polls the job and publishes the same refresh signal for provider-result statuses. The watcher stops at a terminal status or after the existing bounded polling window.

Canceled jobs do not publish a quota refresh because cancellation does not prove that a provider call returned. Queued and running states do not publish because usage is not committed yet.

## Error Handling

Quota refresh requests retain the current fallback behavior. A failed refresh leaves the indicator in its unavailable state and future events, focus, or visibility changes can retry.

Background job watchers stop quietly on API errors because the main page already owns user-facing retry messaging. A later component mount or focus refresh still reconciles quota.

## Testing

Backend tests prove failed provider calls increment used quota and estimated billable usage while preserving failed-call counts.

Frontend tests prove:

- a refresh event triggers a second quota request and updates displayed values;
- multiple mounted quota indicators update from the same event;
- focus and visibility recovery trigger refreshes;
- the watcher publishes once per provider attempt for completed, failed, and retry-scheduled results;
- queued/running/canceled states do not publish;
- upload polling calls the shared notification path.
