# Global Search and Readability Design

## Scope

Fix the authenticated workspace in three areas:

1. Keep the invoice archive project index fully visible without overlapping the primary navigation.
2. Increase the type scale across authenticated pages so routine content can be scanned without strain.
3. Turn the top command search into a working global search for invoices, projects, and suppliers.

## Layout and typography

The invoice archive remains a two-column workbench, but its negative horizontal expansion must stay inside the workspace. The project index receives a stable desktop track and the invoice content track remains shrinkable. The filter toolbar may wrap into fewer columns at intermediate widths so it does not force the project index beneath the primary sidebar.

Authenticated body text, controls, table cells, and navigation use a 14px baseline. Secondary metadata may use 12px, while compact labels may use 11px only when they are not required to complete a task. Existing display headings retain their current hierarchy. Mobile layouts continue to replace the project rail with a horizontal all-invoices control.

## Search architecture

Add `GET /api/v1/search?q=<query>&limit=<per-group-limit>`. The endpoint returns grouped invoice, project, and supplier results. It uses the same visibility rules as invoice and project listing, so normal users see owned/private-visible data while finance and admin roles retain their broader access.

Invoice matching covers invoice number, invoice code, seller name, and buyer name. Project matching covers name and description. Supplier matching aggregates distinct non-empty seller names from visible invoices. Results contain only the display data and navigation identifiers needed by the frontend.

The frontend opens a command dialog from the top search control or `Cmd/Ctrl+K`. Input is debounced before calling the endpoint. Results are grouped by type and support pointer selection, arrow-key navigation, Enter, and Escape. Invoice results navigate to invoice detail. Project results navigate to the invoice archive with `project_id`. Supplier results navigate to the invoice archive with `seller_name`.

## Route and filter flow

Hash routes accept query parameters for the invoice archive. `InvoiceListPage` initializes and updates its filters from `project_id`, `seller_name`, and `q`, while preserving existing local filter behavior. Selecting a global result closes the dialog and updates the hash. Invalid or unavailable identifiers degrade to an empty filtered result instead of breaking the page.

## States and errors

The command dialog has idle guidance, loading, grouped results, no-results, and inline request-error states. Queries shorter than two trimmed characters do not call the server. Stale responses are ignored when the input changes or the dialog closes.

## Verification

Backend tests cover query validation, all three result types, result limits, supplier deduplication, and user visibility. Frontend tests cover dialog activation, keyboard shortcuts, result rendering, navigation, and error/empty states. CSS contract tests enforce the non-overlapping archive geometry and readable minimum type scale. Final browser checks cover desktop and compact widths.
