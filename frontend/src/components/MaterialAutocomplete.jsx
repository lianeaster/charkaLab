import { useEffect, useRef, useState } from "react";
import { api, FORM_LABELS, PIT_LABELS } from "../api";

export default function MaterialAutocomplete({ value, onChange, placeholder }) {
  const [query, setQuery] = useState(value?.name || "");
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState([]);
  const boxRef = useRef(null);

  useEffect(() => {
    setQuery(value?.name || "");
  }, [value?.material_id]);

  useEffect(() => {
    function handleClick(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  useEffect(() => {
    if (!open) return;
    const handle = setTimeout(async () => {
      try {
        const res = await api.suggestMaterials(query);
        setSuggestions(res);
      } catch (_) {
        setSuggestions([]);
      }
    }, 150);
    return () => clearTimeout(handle);
  }, [query, open]);

  async function selectMaterial(m) {
    setQuery(m.name);
    setOpen(false);
    const forms = await api.materialForms(m.id);
    setOptions(forms.options);
    const first = forms.options[0] || { form: "fresh", pit: "na" };
    onChange({
      material_id: m.id,
      name: m.name,
      has_pit_variants: m.has_pit_variants,
      form: first.form,
      pit: first.pit,
      options: forms.options,
    });
  }

  const currentOptions = value?.options || options;
  const forms = [...new Set(currentOptions.map((o) => o.form))];
  const pitsForForm = currentOptions
    .filter((o) => o.form === value?.form)
    .map((o) => o.pit);

  function updateForm(form) {
    const pits = currentOptions.filter((o) => o.form === form).map((o) => o.pit);
    onChange({ ...value, form, pit: pits[0] || "na" });
  }

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
      <div className="relative flex-1" ref={boxRef}>
        <input
          type="text"
          className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm outline-none focus:border-charka-500 focus:ring-1 focus:ring-charka-500"
          placeholder={placeholder || "Почніть вводити назву сировини…"}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
        />
        {open && suggestions.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-stone-200 bg-white shadow-lg">
            {suggestions.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  className="block w-full px-3 py-2 text-left text-sm hover:bg-charka-50"
                  onClick={() => selectMaterial(m)}
                >
                  {m.name}
                  {m.has_pit_variants && (
                    <span className="ml-2 text-xs text-stone-400">(є кісточка)</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {value?.material_id && currentOptions.length > 0 && (
        <div className="flex gap-2">
          <select
            className="rounded-lg border border-stone-300 px-2 py-2 text-sm"
            value={value.form}
            onChange={(e) => updateForm(e.target.value)}
          >
            {forms.map((f) => (
              <option key={f} value={f}>
                {FORM_LABELS[f] || f}
              </option>
            ))}
          </select>
          {pitsForForm.some((p) => p !== "na") && (
            <select
              className="rounded-lg border border-stone-300 px-2 py-2 text-sm"
              value={value.pit}
              onChange={(e) => onChange({ ...value, pit: e.target.value })}
            >
              {pitsForForm.map((p) => (
                <option key={p} value={p}>
                  {PIT_LABELS[p] || p}
                </option>
              ))}
            </select>
          )}
        </div>
      )}
    </div>
  );
}
