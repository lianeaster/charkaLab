import { useEffect, useState } from "react";
import { api, variantLabel } from "../api";
import MaterialAutocomplete from "./MaterialAutocomplete";

// Ролі, які користувач не редагує вручну: основна сировина фіксована,
// а підсолоджувач (цукор/мед) додає й дозує сам двигун при балансуванні.
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

  const [rows, setRows] = useState([]);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  // Ініціалізуємо редаговані рядки зі складу варіанта; підвантажуємо форми
  // кожної сировини, щоб працював випадаючий список форм.
  useEffect(() => {
    let cancelled = false;
    const editable = variant.materials.filter(
      (m) => !LOCKED_ROLES.has(m.role) && m.material_id > 0
    );
    Promise.all(
      editable.map(async (m) => {
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
          role: m.role || "additional",
          options,
        };
      })
    ).then((list) => {
      if (!cancelled) {
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
      const payload = {
        title: variant.title,
        main_material: {
          material_id: request.main_material.material_id,
          part: request.main_material.part,
          form: request.main_material.form,
          pit: request.main_material.pit,
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
          основну сировину й підсолоджувач змінює лише двигун
        </span>
      </div>

      {/* Основна сировина — фіксована */}
      <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm">
        <span className="font-medium text-stone-800">{mainMat?.name}</span>
        <span className="text-xs text-stone-500">· {variantLabel(mainMat)}</span>
        <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[11px] text-stone-500">
          основна · фіксована
        </span>
      </div>

      {!ready ? (
        <p className="text-sm text-stone-400">Завантаження складу…</p>
      ) : (
        <div className="flex flex-col gap-2">
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

      <div className="mt-4 flex items-center gap-2">
        <button
          type="button"
          onClick={apply}
          disabled={busy}
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
      </div>
    </div>
  );
}
