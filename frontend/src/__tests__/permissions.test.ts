import { describe, expect, it } from "vitest";

import { projectCreationModes, visibleNavigationIds } from "../lib/permissions";

describe("visibleNavigationIds", () => {
  it("keeps operational routes for ordinary and finance users", () => {
    expect(visibleNavigationIds("user")).toEqual([
      "dashboard",
      "invoices",
      "upload",
      "review",
      "exports",
    ]);
    expect(visibleNavigationIds("finance")).toEqual([
      "dashboard",
      "invoices",
      "upload",
      "review",
      "exports",
    ]);
  });

  it("adds user administration and OCR settings only for administrators", () => {
    expect(visibleNavigationIds("admin")).toEqual([
      "dashboard",
      "invoices",
      "upload",
      "review",
      "exports",
      "users",
      "settings",
    ]);
  });
});

describe("projectCreationModes", () => {
  it("limits ordinary users to private projects", () => {
    expect(projectCreationModes("user")).toEqual(["private"]);
  });

  it("allows finance and administrators to create shared projects", () => {
    expect(projectCreationModes("finance")).toEqual(["private", "shared"]);
    expect(projectCreationModes("admin")).toEqual(["private", "shared"]);
  });
});
