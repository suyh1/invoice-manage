# Upload OCR Quota Width Design

## Goal

Make the OCR quota panel in the upload page heading the same width as the quota panel in the settings page heading.

## Root Cause

The settings page applies `flex: 0 0 min(360px, 42%)` through `.settings-intro .quota-status`. The upload heading is a two-column grid whose quota column already ranges from 260px to 360px, but the shared editorial heading rule then applies `width: min(330px, 38%)` inside that grid cell. The percentage is calculated from the grid cell, so the panel becomes much narrower than the column.

## Design

Add an upload-page-specific desktop rule that sets the quota panel to `width: 100%`, filling its existing 260px-to-360px grid column. At wide desktop sizes this produces the same 360px panel width as settings without copying a flex percentage into a grid child. Keep the existing responsive rule that expands editorial quota panels to `width: 100%` below 980px.

The component markup, quota data, progress behavior, colors, and sidebar presentation remain unchanged.

## Testing

Add a stylesheet contract assertion that both upload and settings heading selectors use the same width token. Run focused frontend tests, the production build, and browser checks at desktop and narrow viewports to confirm matching width and no overflow.
