# Project Files and ZIP Export Design

## Goal

Allow users to upload non-OCR business files directly into a project, manage them separately from invoices, and download a ZIP containing a selected project's invoice originals and ordinary project files.

## Data model

Reuse `invoice_documents` and add a non-null `document_kind` field with two values:

- `invoice`: existing invoice originals, including files uploaded with OCR temporarily disabled
- `project_file`: ordinary project files that never create OCR jobs or invoice records

Existing rows migrate to `invoice`. Storage keys, hashes, project ownership, upload ownership, status, download access, and audit records remain shared.

## Upload modes

The upload page exposes a segmented mode control:

- Invoice recognition: current validation and OCR workflow
- Project file: requires a project, hides business scene and OCR controls, and always sends `document_kind=project_file` with `auto_ocr=false`

Project files accept PDF, PNG, JPG, JPEG, DOCX, and XLSX up to 50 MiB. OOXML files are verified as ZIP containers with the expected Word or Excel package entries. Executable or mismatched files are rejected.

## Project file view

The invoice archive adds `发票` and `项目文件` views. The project-file view follows the current project selection and lists filename, type, size, uploader, and upload time. Users can download files and soft-delete files they are allowed to manage. Finance and administrators can see all accessible project files; regular users see their own uploads, matching current document access rules.

## ZIP export

The existing export task system gains a project-package ZIP path. ZIP creation requires one project and ignores invoice status and OCR metadata options. The archive contains:

- `发票原件/`: invoice documents in the selected project that the export creator can access
- `项目文件/`: ordinary project files in the selected project that the export creator can access
- `manifest.json`: project identity and each file's archive path, document id, original filename, kind, MIME type, size, SHA256, uploader, and upload time

Names are normalized to basenames and duplicate names receive deterministic numeric suffixes. Missing storage files fail the task instead of silently producing an incomplete package. Existing XLSX, CSV, and JSON exports remain structured invoice-data exports.

## API and permissions

`POST /api/v1/documents` accepts `document_kind`. `GET /api/v1/documents` lists visible project files with optional `project_id`, and `DELETE /api/v1/documents/{id}` soft-deletes only ordinary project files. Existing preview and download endpoints remain unchanged.

`POST /api/v1/exports` accepts `format=zip` only with a project filter. Export task list and download permissions remain unchanged.

## Errors and audit

Validation returns specific type, mismatch, and size errors. Upload, project-file deletion, export creation, completion, and failure continue to use audit logging. ZIP errors expose only safe task error messages.

## Verification

Backend tests cover migration defaults, project-file validation, upload without OCR, list/delete permissions, ZIP paths, duplicate names, manifest contents, missing source files, and download access. Frontend tests cover upload modes, validation profiles, project-file listing, ZIP export controls, and responsive layouts. Browser verification checks desktop and mobile upload, archive, and export flows without page overflow.
