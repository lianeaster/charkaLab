import { useEffect, useState } from "react";
import { api } from "./api";
import MaterialAutocomplete from "./components/MaterialAutocomplete";
import AdditionalMaterials from "./components/AdditionalMaterials";
import BaseSelector from "./components/BaseSelector";
import ProfileSelector from "./components/ProfileSelector";
import RecipeResults from "./components/RecipeResults";

function Section({ step, title, hint, children }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
      <div className="mb-3">
        <h2 className="text-base font-semibold text-stone-800">
          <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-macerate-600 text-xs text-white">
            {step}
          </span>
          {title}
        </h2>
        {hint && <p className="mt-1 text-sm text-stone-500">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

export default function App() {
  const [characteristics, setCharacteristics] = useState([]);
  const [bases, setBases] = useState([]);

  const [mainMaterial, setMainMaterial] = useState(null);
  const [additional, setAdditional] = useState([]);
  const [baseId, setBaseId] = useState(null);
  const [desired, setDesired] = useState([]);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.characteristics().then(setCharacteristics).catch(() => {});
    api.bases().then(setBases).catch(() => {});
  }, []);

  const canSubmit = mainMaterial?.material_id && !loading;

  async function handleGenerate() {
    setError(null);
    setLoading(true);
    setResult(null);
    try {
      const payload = {
        main_material: {
          material_id: mainMaterial.material_id,
          form: mainMaterial.form,
          pit: mainMaterial.pit,
        },
        additional_materials: additional
          .filter((a) => a.material_id)
          .map((a) => ({ material_id: a.material_id, form: a.form, pit: a.pit })),
        base_id: baseId,
        desired_characteristics: desired,
      };
      const res = await api.generate(payload);
      setResult(res);
    } catch (e) {
      setError(e.message || "Помилка генерації");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-stone-900">charkaLab</h1>
        <p className="text-stone-500">
          Генератор рецептів мацератів на основі ароматичних сполук
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <Section
          step={1}
          title="Основна сировина"
          hint="Почніть вводити назву — підкаже по перших літерах."
        >
          <MaterialAutocomplete value={mainMaterial} onChange={setMainMaterial} />
        </Section>

        <Section
          step={2}
          title="Допоміжна сировина"
          hint="Необов'язково. До 10 рядків, кожен з формою та (за потреби) кісточкою."
        >
          <AdditionalMaterials rows={additional} onChange={setAdditional} />
        </Section>

        <Section step={3} title="Основа напою">
          <BaseSelector bases={bases} value={baseId} onChange={setBaseId} />
        </Section>

        <Section
          step={4}
          title="Бажаний профіль напою"
          hint="Які характеристики має мати напій?"
        >
          <ProfileSelector
            characteristics={characteristics}
            selected={desired}
            onChange={setDesired}
          />
        </Section>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={!canSubmit}
          className="rounded-xl bg-macerate-600 px-6 py-3 text-base font-semibold text-white shadow hover:bg-macerate-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Генерація…" : "Згенерувати рецепти"}
        </button>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-2">
            <h2 className="mb-3 text-lg font-semibold text-stone-800">
              Запропоновані композиції
            </h2>
            <RecipeResults result={result} />
          </div>
        )}
      </div>
    </div>
  );
}
