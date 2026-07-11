// @vitest-environment jsdom

import { cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useHashRoute } from "../app/router";


afterEach(() => {
  cleanup();
  window.location.hash = "#/";
});

describe("invoice archive route parameters", () => {
  it("preserves global-search filters from the hash query", () => {
    window.location.hash = "#/invoices?project_id=project-1&seller_name=%E4%BA%91%E6%A0%96&q=1287";

    const { result } = renderHook(() => useHashRoute("user"));

    expect(result.current.id).toBe("invoices");
    expect(result.current.params).toEqual({
      projectId: "project-1",
      sellerName: "云栖",
      q: "1287",
    });
  });
});
