// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const indexHtml = readFileSync(new URL("../../index.html", import.meta.url), "utf8");

describe("brand metadata", () => {
  it("declares browser and installed-app icon assets", () => {
    expect(indexHtml).toContain('rel="icon" type="image/svg+xml" href="/favicon.svg"');
    expect(indexHtml).toContain('rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png"');
    expect(indexHtml).toContain('rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png"');
    expect(indexHtml).toContain('rel="manifest" href="/site.webmanifest"');
    expect(indexHtml).toContain('name="theme-color" content="#0a0a0a"');
  });
});
