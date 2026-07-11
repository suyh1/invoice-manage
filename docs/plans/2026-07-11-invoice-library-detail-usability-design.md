# Invoice Library and Detail Usability Design

## Goal

Fix the broken project selection state, simplify and resize the invoice result table, keep the invoice detail workbench inside the application workspace, and separate archive metadata from OCR-derived fields.

## Project index

The active state belongs to the complete project row. The project selection button and row actions must inherit the row foreground and background instead of painting nested light surfaces. Hover and keyboard focus keep the edit and archive actions visible without changing the row dimensions.

## Invoice result table

The result table contains five columns:

- Invoice number, with status shown as secondary metadata
- Seller
- Invoice date
- Amount
- Fixed-width action column

The first four columns expose a pointer-accessible resize handle in the header. Widths are bounded to useful minimums and persisted in local storage. Long seller names and invoice numbers stay on one line with ellipsis and a title containing the full value. The action column is not resizable.

## Invoice detail layout

The detail workbench remains within `.workspace`, below the top bar and to the right of the main navigation. It no longer relies on negative margins that extend into the application chrome. Desktop uses a bounded two-column grid, medium screens reduce the preview share, and narrow screens stack the preview and editor.

## OCR field presentation

OCR helper text is provider-independent:

`原始字段：<source field or 未返回> · OCR值：<raw value or 无值>`

Business scene is archive metadata, not an OCR field. It is removed from `FieldEditor` and placed beside project assignment using the same options as the upload page.

Invoice code and invoice number remain distinct in the data model because traditional Chinese VAT invoices may contain both. Invoice code is removed from the compact list and is shown in detail only when OCR or saved invoice data contains a value.

## Data flow

Project and business-scene changes use the existing invoice PATCH endpoint. Each control sends only its changed field. Successful responses replace the local detail state; failures retain the prior selection and show the existing inline error message. Field correction saves no longer include business scene.

## Verification

Frontend tests cover the compact columns, resize handles, persisted widths, active project styling, bounded detail layout, provider-independent OCR labels, conditional invoice-code display, and business-scene PATCH behavior. Existing backend tests verify that `invoice_code` and `expense_scene` remain supported. Browser screenshots verify desktop and narrow layouts without overlap or horizontal overflow.
