import { describe, expect, it } from "vitest";

import { groupProjects, type ProjectSummary } from "../lib/projects";

const projects: ProjectSummary[] = [
  {
    id: "uncategorized",
    name: "未分类",
    description: "未指定项目的发票",
    visibility: "system",
    status: "active",
    system_key: "uncategorized",
    created_by: null,
    created_at: null,
    updated_at: null,
    archived_at: null,
    can_manage: false,
  },
  {
    id: "shared",
    name: "共享差旅",
    description: null,
    visibility: "shared",
    status: "active",
    system_key: null,
    created_by: "finance-id",
    created_at: null,
    updated_at: null,
    archived_at: null,
    can_manage: true,
  },
  {
    id: "private",
    name: "我的采购",
    description: null,
    visibility: "private",
    status: "active",
    system_key: null,
    created_by: "owner-id",
    created_at: null,
    updated_at: null,
    archived_at: null,
    can_manage: true,
  },
  {
    id: "archived",
    name: "历史项目",
    description: null,
    visibility: "shared",
    status: "archived",
    system_key: null,
    created_by: "finance-id",
    created_at: null,
    updated_at: null,
    archived_at: "2026-07-10T00:00:00Z",
    can_manage: true,
  },
];

describe("groupProjects", () => {
  it("separates system, shared, private, and archived projects", () => {
    const grouped = groupProjects(projects);

    expect(grouped.system.map((project) => project.id)).toEqual(["uncategorized"]);
    expect(grouped.shared.map((project) => project.id)).toEqual(["shared"]);
    expect(grouped.private.map((project) => project.id)).toEqual(["private"]);
    expect(grouped.archived.map((project) => project.id)).toEqual(["archived"]);
  });

  it("sorts each group by Chinese project name without mutating the input", () => {
    const input = [
      { ...projects[1], id: "z", name: "差旅二组" },
      { ...projects[1], id: "a", name: "差旅一组" },
    ];
    const original = input.map((project) => project.id);

    expect(groupProjects(input).shared.map((project) => project.id)).toEqual(["a", "z"]);
    expect(input.map((project) => project.id)).toEqual(original);
  });
});
