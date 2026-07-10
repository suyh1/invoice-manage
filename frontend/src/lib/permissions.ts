import type { UserRole } from "../auth/authState";

export type NavigationId =
  | "dashboard"
  | "invoices"
  | "upload"
  | "review"
  | "exports"
  | "projects"
  | "users"
  | "settings";

export type ProjectCreationMode = "private" | "shared";

const operationalNavigation: NavigationId[] = [
  "dashboard",
  "invoices",
  "upload",
  "review",
  "exports",
  "projects",
];

export function visibleNavigationIds(role: UserRole): NavigationId[] {
  if (role !== "admin") {
    return [...operationalNavigation];
  }
  return [...operationalNavigation, "users", "settings"];
}

export function projectCreationModes(role: UserRole): ProjectCreationMode[] {
  return role === "user" ? ["private"] : ["private", "shared"];
}

export function canManageUsers(role: UserRole): boolean {
  return role === "admin";
}
