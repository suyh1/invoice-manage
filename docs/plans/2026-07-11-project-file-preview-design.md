# Project File Preview Design

## Goal

Allow users to preview ordinary project files from the project-file view without disrupting download and delete workflows.

## Interaction

Each project-file row adds a preview action before download and delete.

- PDF, PNG, JPG, and JPEG open in a modal inside the invoice archive.
- Images use an image element with contained sizing.
- PDFs use an iframe backed by the existing document preview endpoint.
- DOCX and XLSX open the existing preview endpoint in a new browser window because browsers do not provide stable native inline rendering for these formats.
- The modal includes the filename, an open-in-new-window action, a download action, and a close action.

## Architecture

Reuse `GET /api/v1/documents/{document_id}/preview`; it already checks document access and returns the original file with inline disposition. Add a focused `ProjectFilePreviewDialog` frontend component and keep `ProjectFileTable` responsible only for selecting the active file.

No document parsing dependency is added. This avoids inaccurate Office layout conversion, additional bundle weight, and unsafe HTML rendering.

## Responsive Behavior

The modal is constrained to the viewport. Its preview canvas scrolls internally, while the page remains free of horizontal overflow. On mobile, the modal uses nearly the full viewport and keeps actions in a compact toolbar.

## Testing

Frontend tests cover:

- Preview action accessibility and URL behavior.
- PDF and image modal rendering.
- DOCX/XLSX new-window preview links.
- Closing the modal.
- Existing download and two-step delete behavior.
