# Global Search and Readability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep the invoice project index fully visible, raise authenticated UI readability, and implement permission-aware global search for invoices, projects, and suppliers.

**Architecture:** Add a grouped FastAPI search endpoint backed by existing invoice/project visibility rules, then connect it to a React command dialog opened from the application shell. Route query parameters carry project and supplier selections into the existing invoice list. Finish with scoped CSS corrections that remove archive overlap and establish readable authenticated type sizes.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, React 19, TypeScript, Vitest, Testing Library, CSS, pytest.

---

### Task 1: Backend global search contract

**Files:**
- Create: `backend/app/api/routes/search.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/domain/invoice/service.py`
- Test: `backend/tests/test_global_search.py`

**Step 1: Write the failing endpoint tests**

Add tests that seed visible and hidden invoices/projects and assert:

```python
response = client.get("/api/v1/search", params={"q": "云栖"})
assert response.status_code == 200
assert response.json()["data"]["invoices"][0]["seller_name"] == "上海云栖酒店"
assert response.json()["data"]["suppliers"] == [{"name": "上海云栖酒店", "invoice_count": 1}]
```

Add separate assertions for project matches, supplier deduplication, per-group limits, a query shorter than two characters, and exclusion of another normal user's records.

**Step 2: Run tests to verify RED**

Run: `cd backend && .venv/bin/pytest tests/test_global_search.py -q`

Expected: FAIL because `/api/v1/search` does not exist.

**Step 3: Implement minimal search service and route**

Reuse the invoice visibility predicate or query construction already used by `InvoiceService.list_invoices`. Return:

```python
{
    "data": {
        "invoices": [{"id": "...", "invoice_number": "...", "seller_name": "...", "buyer_name": "...", "amount_with_tax": "..."}],
        "projects": [{"id": "...", "name": "...", "description": "..."}],
        "suppliers": [{"name": "...", "invoice_count": 1}],
    }
}
```

Validate `q` with `min_length=2`, trim it, cap `limit` to a small per-group range, and register the router before the static frontend mount.

**Step 4: Run tests to verify GREEN**

Run: `cd backend && .venv/bin/pytest tests/test_global_search.py tests/test_invoice_api.py tests/test_projects.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/app/api/routes/search.py backend/app/main.py backend/app/domain/invoice/service.py backend/tests/test_global_search.py
git commit -m "feat: add permission-aware global search"
```

### Task 2: Search result routing

**Files:**
- Modify: `frontend/src/app/router.tsx`
- Modify: `frontend/src/pages/InvoiceListPage.tsx`
- Test: `frontend/src/__tests__/router.test.tsx`
- Test: `frontend/src/__tests__/invoiceWorkbench.test.ts`

**Step 1: Write failing route/filter tests**

Test that invoice archive hashes retain `project_id`, `seller_name`, and `q`, and that the invoice page reads these values into its initial API query.

**Step 2: Run tests to verify RED**

Run: `cd frontend && npm test -- --run src/__tests__/router.test.tsx src/__tests__/invoiceWorkbench.test.ts`

Expected: FAIL because route query parameters are currently discarded.

**Step 3: Implement minimal route parsing**

Parse the hash with `URLSearchParams`, keep the base route comparison stable, and expose search parameters on `AppRoute.params`. Initialize `InvoiceListPage` filters from the route parameters and include `seller_name` in its API query.

**Step 4: Run tests to verify GREEN**

Run: `cd frontend && npm test -- --run src/__tests__/router.test.tsx src/__tests__/invoiceWorkbench.test.ts`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/app/router.tsx frontend/src/pages/InvoiceListPage.tsx frontend/src/__tests__/router.test.tsx frontend/src/__tests__/invoiceWorkbench.test.ts
git commit -m "feat: route global search results into invoice filters"
```

### Task 3: Global search command dialog

**Files:**
- Create: `frontend/src/components/GlobalSearchDialog.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/__tests__/GlobalSearchDialog.test.tsx`

**Step 1: Write failing interaction tests**

Test opening from the top button, `Cmd/Ctrl+K`, debounced API loading, grouped result labels, arrow-key selection, Enter navigation, Escape close, empty results, and request errors.

**Step 2: Run tests to verify RED**

Run: `cd frontend && npm test -- --run src/__tests__/GlobalSearchDialog.test.tsx`

Expected: FAIL because the dialog does not exist.

**Step 3: Implement minimal accessible dialog**

Use a native dialog-like overlay with `role="dialog"`, an autofocus search input, grouped result buttons, a single active-index list, request cancellation/stale-response protection, and a 200ms debounce. Navigate with `window.location.hash` and close after selection.

**Step 4: Run tests to verify GREEN**

Run: `cd frontend && npm test -- --run src/__tests__/GlobalSearchDialog.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/GlobalSearchDialog.tsx frontend/src/components/AppShell.tsx frontend/src/styles.css frontend/src/__tests__/GlobalSearchDialog.test.tsx
git commit -m "feat: implement global search command dialog"
```

### Task 4: Archive geometry and authenticated type scale

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/__tests__/responsiveLayout.test.ts`
- Modify: `frontend/src/__tests__/authenticatedVisualSystem.test.tsx`

**Step 1: Write failing CSS contract tests**

Assert that the final archive rule no longer uses a negative left margin, its project track is at least 220px on desktop, the right toolbar can wrap at narrower desktop widths, and authenticated navigation/body/table/control text meets the approved size floor.

**Step 2: Run tests to verify RED**

Run: `cd frontend && npm test -- --run src/__tests__/responsiveLayout.test.ts src/__tests__/authenticatedVisualSystem.test.tsx`

Expected: FAIL against the current negative-margin and small-type rules.

**Step 3: Implement scoped CSS corrections**

Keep the archive flush with the workspace's left content boundary, use a stable `232px minmax(0, 1fr)` grid, and recover right-side space through responsive toolbar columns and horizontal table scrolling. Add a final authenticated readability layer with 14px routine text, 12px secondary metadata, appropriately larger controls, and unchanged display-heading hierarchy.

**Step 4: Run tests to verify GREEN**

Run: `cd frontend && npm test -- --run src/__tests__/responsiveLayout.test.ts src/__tests__/authenticatedVisualSystem.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/styles.css frontend/src/__tests__/responsiveLayout.test.ts frontend/src/__tests__/authenticatedVisualSystem.test.tsx
git commit -m "fix: improve archive layout and authenticated readability"
```

### Task 5: Full verification and browser review

**Files:**
- Modify only if verification exposes a defect.

**Step 1: Run backend tests**

Run: `cd backend && .venv/bin/pytest -q`

Expected: PASS.

**Step 2: Run frontend tests and build**

Run: `cd frontend && npm test -- --run`

Expected: PASS.

Run: `cd frontend && npm run build`

Expected: PASS.

**Step 3: Start the application**

Use the repository's documented development commands. Do not reuse a port already in use.

**Step 4: Verify in browser**

At desktop and compact widths, confirm the project index is fully visible, no required text is below the approved scale, the command dialog opens by click and keyboard, and each result type lands on the correct page/filter.

**Step 5: Commit verification fixes if needed**

```bash
git add <verified-files>
git commit -m "fix: address global search verification findings"
```
