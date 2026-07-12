// @vitest-environment jsdom

import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BrandMark } from "../components/BrandMark";

afterEach(() => {
  cleanup();
});

describe("BrandMark", () => {
  it("renders the shared decorative invoice scanning mark", () => {
    const { container } = render(<BrandMark className="test-brand-mark" />);
    const mark = container.querySelector("svg[data-brand-mark]");

    expect(mark).toBeTruthy();
    expect(mark?.getAttribute("aria-hidden")).toBe("true");
    expect(mark?.getAttribute("class")).toContain("test-brand-mark");
    expect(mark?.querySelector("[data-brand-invoice]")).toBeTruthy();
    expect(mark?.querySelectorAll("[data-brand-scan-corner]")).toHaveLength(4);
  });
});
