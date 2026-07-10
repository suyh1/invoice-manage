// @ts-expect-error Vitest runs in Node; the browser app intentionally omits Node type declarations.
import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const styles = readFileSync(new URL("../styles.css", import.meta.url), "utf8");

describe("responsive workspace layout", () => {
  it("keeps the workspace grid track shrinkable at intermediate widths", () => {
    const workspaceRule = styles.match(/\.workspace\s*\{([^}]*)\}/)?.[1];

    expect(workspaceRule).toContain("grid-template-columns: minmax(0, 1fr);");
  });

  it("keeps page content and invoice filters within tablet widths", () => {
    const pageStackRule = styles.match(/\.page-stack\s*\{([^}]*)\}/)?.[1];
    const tabletRules = styles.match(/@media \(max-width: 980px\) \{([\s\S]*?)@media \(max-width: 680px\)/)?.[1];

    expect(pageStackRule).toContain("grid-template-columns: minmax(0, 1fr);");
    expect(tabletRules).toMatch(
      /\.invoice-filters\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\);/,
    );
  });
});
