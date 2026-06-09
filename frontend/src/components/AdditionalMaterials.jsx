import MaterialAutocomplete from "./MaterialAutocomplete";

const MAX_ROWS = 10;

export default function AdditionalMaterials({ rows, onChange }) {
  function addRow() {
    if (rows.length >= MAX_ROWS) return;
    onChange([...rows, { material_id: null, name: "", form: "fresh", pit: "na" }]);
  }

  function updateRow(index, value) {
    const next = rows.slice();
    next[index] = value;
    onChange(next);
  }

  function removeRow(index) {
    onChange(rows.filter((_, i) => i !== index));
  }

  return (
    <div className="flex flex-col gap-3">
      {rows.map((row, i) => (
        <div key={i} className="flex items-start gap-2">
          <div className="flex-1">
            <MaterialAutocomplete
              value={row}
              onChange={(v) => updateRow(i, v)}
              placeholder={`Додаткова сировина #${i + 1}`}
            />
          </div>
          <button
            type="button"
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-500 hover:bg-stone-100"
            onClick={() => removeRow(i)}
            title="Видалити рядок"
          >
            ×
          </button>
        </div>
      ))}

      <button
        type="button"
        className="self-start rounded-lg border border-dashed border-macerate-500 px-4 py-2 text-sm font-medium text-macerate-600 hover:bg-macerate-50 disabled:cursor-not-allowed disabled:opacity-40"
        onClick={addRow}
        disabled={rows.length >= MAX_ROWS}
      >
        + Додати сировину{rows.length > 0 ? ` (${rows.length}/${MAX_ROWS})` : ""}
      </button>
    </div>
  );
}
