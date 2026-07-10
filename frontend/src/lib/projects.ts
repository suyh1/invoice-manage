export type ProjectVisibility = "private" | "shared" | "system";
export type ProjectStatus = "active" | "archived";

export type ProjectSummary = {
  id: string;
  name: string;
  description: string | null;
  visibility: ProjectVisibility;
  status: ProjectStatus;
  system_key: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  archived_at: string | null;
  can_manage: boolean;
};

export type ProjectGroups = {
  system: ProjectSummary[];
  shared: ProjectSummary[];
  private: ProjectSummary[];
  archived: ProjectSummary[];
};

export type AssignableProjectGroups = Pick<ProjectGroups, "system" | "shared" | "private">;

const projectNameCollator = new Intl.Collator("zh-CN-u-co-stroke");

export function groupProjects(projects: ProjectSummary[]): ProjectGroups {
  const groups: ProjectGroups = { system: [], shared: [], private: [], archived: [] };
  for (const project of projects) {
    if (project.status === "archived") {
      groups.archived.push(project);
    } else {
      groups[project.visibility].push(project);
    }
  }

  for (const group of Object.values(groups)) {
    group.sort((left, right) => projectNameCollator.compare(left.name, right.name));
  }
  return groups;
}

export function groupAssignableProjectOptions(projects: ProjectSummary[]): AssignableProjectGroups {
  const grouped = groupProjects(projects);
  return { system: grouped.system, shared: grouped.shared, private: grouped.private };
}
