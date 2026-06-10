import { useEffect, useRef, useState } from "react";
import { api, variantLabel } from "../api";

function variantKey(o) {
  return `${o.part || "whole"}|${o.form}|${o.pit}`;
}

export default function MaterialAutocomplete({
  value,
  onChange,
  placeholder,
  forbiddenTags,
}) {
  const [query, setQuery] = useState(value?.name || "");
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [options, setOptions] = useState([]);
  const boxRef = useRef(null);

  useEffect(() => {
    // Синхронізуємо текст лише коли є реальний вибір; при скиданні
    // (value=null) не затираємо те, що користувач друкує.
    if (value?.material_id) setQuery(value.name || "");
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
        const blocked = new Set(forbiddenTags || []);
        const filtered =
          blocked.size === 0
            ? res
            : res.filter((m) => !(m.tags || []).some((t) => blocked.has(t)));
        setSuggestions(filtered);
      } catch (_) {
        setSuggestions([]);
      }
    }, 150);
    return () => clearTimeout(handle);
  }, [query, open, forbiddenTags]);

  function handleInput(text) {
    setQuery(text);
    setOpen(true);
    // Текст розійшовся з вибраною сировиною → скидаємо вибір,
    // щоб не згенерувати рецепт по застарілому матеріалі.
    if (value?.material_id && text.trim() !== value.name) {
      onChange(null);
      setOptions([]);
    }
  }

  const trimmed = query.trim();
  const noMatch =
    open && trimmed.length > 0 && suggestions.length === 0 && !value?.material_id;

  async function selectMaterial(m) {
    setQuery(m.name);
    setOpen(false);
    const forms = await api.materialForms(m.id);
    setOptions(forms.options);
    const first = forms.options[0] || { part: "whole", form: "fresh", pit: "na" };
    onChange({
      material_id: m.id,
      name: m.name,
      has_pit_variants: m.has_pit_variants,
      tags: m.tags || [],
      part: first.part || "whole",
      form: first.form,
      pit: first.pit,
      options: forms.options,
    });
  }

  const currentOptions = value?.options || options;

  function updateVariant(key) {
    const o = currentOptions.find((x) => variantKey(x) === key);
    if (!o) return;
    onChange({ ...value, part: o.part || "whole", form: o.form, pit: o.pit });
  }

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
      <div className="relative flex-1" ref={boxRef}>
        <input
          type="text"
          className={
            "w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-1 " +
            (noMatch
              ? "border-red-300 focus:border-red-400 focus:ring-red-400"
              : "border-stone-300 focus:border-charka-500 focus:ring-charka-500")
          }
          placeholder={placeholder || "Почніть вводити назву сировини…"}
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          onFocus={() => setOpen(true)}
        />
        {noMatch && (
          <p className="mt-1 text-xs text-red-600">
            Немає такої сировини в базі. Оберіть зі списку.
          </p>
        )}
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
                  {m.aliases && m.aliases.length > 0 && (
                    <span className="ml-2 text-xs text-stone-400">
                      ({m.aliases.join(", ")})
                    </span>
                  )}
                  {m.has_pit_variants && (
                    <span className="ml-2 text-xs text-stone-400">· є кісточка</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {value?.material_id && currentOptions.length > 0 && (
        <select
          className="rounded-lg border border-stone-300 px-2 py-2 text-sm sm:w-56"
          value={variantKey({ part: value.part, form: value.form, pit: value.pit })}
          onChange={(e) => updateVariant(e.target.value)}
        >
          {currentOptions.map((o) => (
            <option key={variantKey(o)} value={variantKey(o)}>
              {variantLabel(o)}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
