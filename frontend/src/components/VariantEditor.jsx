import { useEffect, useState } from "react";
import { api } from "../api";
import MaterialAutocomplete from "./MaterialAutocomplete";

// Основну сировину редагуємо окремим полем (вона йде в запит як main_material,
// а не в загальний список), тож зі списку рядків її виключаємо. Підсолоджувач
// (цукор/мед) не редагується взагалі — його додає й дозує сам двигун під час
// балансування смаку, вже під новий склад.
const LOCKED_ROLES = new Set(["main", "sweetener"]);

function emptyRow() {
  return {
    material_id: null,
    name: "",
    part: "whole",
    form: "fresh",
    pit: "na",
    role: "additional",
    options: [],
  };
}

export default function VariantEditor({
  variant,
  request,
  forbiddenTags,
  onApply,
  onCancel,
}) {
  const mainMat = variant.materials.find((m) => m.role === "main");
  const sweeteners = variant.materials.filter((m) => m.role === "sweetener");

  const [main, setMain] = useState(null);
  const [rows, setRows] = useState([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  // Ініціалізуємо редаговані поля зі складу варіанта; підвантажуємо форми
  // кожної сировини, щоб працював випадаючий список форм.
  useEffect(() => {
    let cancelled = false;

    async function load(m, role) {
      let options = [];
      try {
        options = (await api.materialForms(m.material_id)).options || [];
      } catch (_) {
        options = [];
      }
      return {
        material_id: m.material_id,
        name: m.name,
        part: m.part || "whole",
        form: m.form,
        pit: m.pit,
        role,
        options,
      };
    }

    const editable = variant.materials.filter(
      (m) => !LOCKED_ROLES.has(m.role) && m.material_id > 0
    );
    Promise.all([
      mainMat?.material_id > 0 ? load(mainMat, "main") : Promise.resolve(null),
      ...editable.map((m) => load(m, m.role || "additional")),
    ]).then(([mainRow, ...list]) => {
      if (!cancelled) {
        setMain(mainRow);
        setRows(list);
        setReady(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [variant]);

  function updateRow(i, value) {
    setRows((prev) =>
      prev.map((r, idx) =>
        idx === i ? { ...value, role: r.role || "additional" } : r
      )
    );
  }

  function removeRow(i) {
    setRows((prev) => prev.filter((_, idx) => idx !== i));
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow()]);
  }

  async function apply() {
    setBusy(true);
    setErr(null);
    try {
      // Основну сировину беремо з редактора (користувач міг її замінити);
      // якщо з якоїсь причини її не завантажено — лишається та, з якою
      // генерувався рецепт.
      const mainSel = main?.material_id ? main : request.main_material;
      const payload = {
        title: variant.title,
        main_material: {
          material_id: mainSel.material_id,
          part: mainSel.part || "whole",
          form: mainSel.form,
          pit: mainSel.pit,
        },
        materials: rows
          .filter((r) => r && r.material_id)
          .map((r) => ({
            material_id: r.material_id,
            part: r.part || "whole",
            form: r.form,
            pit: r.pit,
            role: r.role || "additional",
          })),
        base_id: request.base_id ?? null,
        desired_characteristics: request.desired_characteristics || [],
        audience_id: request.audience_id ?? null,
        season: request.season ?? null,
      };
      const nv = await api.recompute(payload);
      onApply(nv);
    } catch (e) {
      setErr(e.message || "Не вдалося перерахувати");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-4 rounded-xl border border-charka-200 bg-charka-50/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-charka-700">
          Редагування складу
        </h4>
        <span className="text-[11px] text-stone-400">
          підсолоджувач додає й дозує двигун
        </span>
      </div>

      {!ready ? (
        <p className="text-sm text-stone-400">Завантаження складу…</p>
      ) : (
        <div className="flex flex-col gap-2">
          {/* Основна сировина — теж редагована */}
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <MaterialAutocomplete
                value={main}
                onChange={(v) => setMain(v ? { ...v, role: "main" } : null)}
                placeholder="Основна сировина"
                forbiddenTags={forbiddenTags}
              />
            </div>
            <span className="mt-2 shrink-0 rounded-full bg-stone-100 px-2 py-1 text-[11px] text-stone-500">
              основна
            </span>
          </div>

          {rows.map((row, i) => (
            <div key={i} className="flex items-start gap-2">
              <div className="flex-1">
                <MaterialAutocomplete
                  value={row}
                  onChange={(v) => updateRow(i, v)}
                  placeholder={`Інгредієнт #${i + 1}`}
                  forbiddenTags={forbiddenTags}
                />
              </div>
              <button
                type="button"
                className="rounded-lg border border-stone-300 px-3 py-2 text-sm text-stone-500 hover:bg-red-50 hover:text-red-600"
                onClick={() => removeRow(i)}
                title="Видалити інгредієнт"
              >
                ×
              </button>
            </div>
          ))}

          <button
            type="button"
            className="self-start rounded-lg border border-dashed border-charka-500 px-4 py-2 text-sm font-medium text-charka-600 hover:bg-charka-50"
            onClick={addRow}
          >
            + Додати інгредієнт
          </button>
        </div>
      )}

      {sweeteners.length > 0 && (
        <p className="mt-3 text-xs text-stone-400">
          Підсолоджувач ({sweeteners.map((s) => s.name).join(", ")}) додається й
          дозується автоматично під новий склад.
        </p>
      )}

      {err && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={apply}
          disabled={busy || !main?.material_id}
          className="rounded-lg bg-charka-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-charka-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Перерахунок…" : "Оновити"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={busy}
          className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-600 hover:bg-stone-100 disabled:opacity-40"
        >
          Скасувати
        </button>
        {ready && !main?.material_id && (
          <span className="text-xs text-stone-400">
            Оберіть основну сировину зі списку, щоб перерахувати
          </span>
        )}
      </div>
    </div>
  );
}
