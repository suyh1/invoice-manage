import { groupAssignableProjectOptions, type ProjectSummary } from "../lib/projects";

type ProjectFilterProps = {
  label: string;
  projects: ProjectSummary[];
  value: string;
  onChange: (projectId: string) => void;
  includeAll?: boolean;
  required?: boolean;
  disabled?: boolean;
};

export function ProjectFilter({
  label,
  projects,
  value,
  onChange,
  includeAll = true,
  required = false,
  disabled = false,
}: ProjectFilterProps) {
  const groups = groupAssignableProjectOptions(projects);
  return (
    <label>
      {label}
      <select disabled={disabled} required={required} value={value} onChange={(event) => onChange(event.currentTarget.value)}>
        {includeAll ? <option value="">全部项目</option> : null}
        {!includeAll && !value ? <option value="">选择项目</option> : null}
        {groups.system.length ? (
          <optgroup label="系统项目">
            {groups.system.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </optgroup>
        ) : null}
        {groups.shared.length ? (
          <optgroup label="共享项目">
            {groups.shared.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </optgroup>
        ) : null}
        {groups.private.length ? (
          <optgroup label="私有项目">
            {groups.private.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </optgroup>
        ) : null}
      </select>
    </label>
  );
}
