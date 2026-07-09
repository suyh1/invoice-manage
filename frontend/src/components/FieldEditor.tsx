export type EditableField = {
  group: string;
  label: string;
  name: string;
  ocrValue: string | null;
  type?: "date" | "number" | "text";
  value: string;
};

export function FieldEditor({
  fields,
  onChange,
}: {
  fields: EditableField[];
  onChange: (name: string, value: string) => void;
}) {
  const groups = groupFields(fields);

  return (
    <div className="field-editor">
      {groups.map((group) => (
        <section className="field-group" key={group.name}>
          <div className="field-group-heading">
            <span className="section-label">{group.name}</span>
          </div>
          <div className="field-grid">
            {group.fields.map((field) => (
              <label className={field.ocrValue !== null && field.ocrValue !== field.value ? "field-diff" : ""} key={field.name}>
                {field.label}
                <input
                  type={field.type ?? "text"}
                  value={field.value}
                  onChange={(event) => onChange(field.name, event.currentTarget.value)}
                />
                <small>OCR 原值：{field.ocrValue || "-"}</small>
              </label>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function groupFields(fields: EditableField[]) {
  const groups: Array<{ fields: EditableField[]; name: string }> = [];
  fields.forEach((field) => {
    let group = groups.find((candidate) => candidate.name === field.group);
    if (!group) {
      group = { fields: [], name: field.group };
      groups.push(group);
    }
    group.fields.push(field);
  });
  return groups;
}
