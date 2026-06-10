import { useEffect, useMemo, useState } from "react";
import { api, NON_ALCOHOLIC_BASES } from "./api";
import logo from "./assets/logo.png";
import MaterialAutocomplete from "./components/MaterialAutocomplete";
import AdditionalMaterials from "./components/AdditionalMaterials";
import AudienceSelector from "./components/AudienceSelector";
import BaseSelector from "./components/BaseSelector";
import ProfileSelector from "./components/ProfileSelector";
import RecipeResults from "./components/RecipeResults";

function Section({ step, title, hint, children }) {
  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
      <div className="mb-3">
        <h2 className="text-base font-semibold text-stone-800">
          <span className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-charka-600 text-xs text-white">
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
  const [audiences, setAudiences] = useState([]);

  const [audienceId, setAudienceId] = useState("adults");
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
    api.audiences().then(setAudiences).catch(() => {});
  }, []);

  const audienceById = useMemo(() => {
    const map = {};
    for (const a of audiences) map[a.id] = a;
    return map;
  }, [audiences]);
  const audience = audienceById[audienceId];
  const alcoholFree = Boolean(audience?.alcohol_free);
  const forbiddenTags = useMemo(
    () => audience?.forbidden_tags || [],
    [audience],
  );
  const mainMaterialId = mainMaterial?.material_id ?? null;

  // Якщо обрана основна сировина протипоказана поточній ЦА — повертаємось до
  // «дорослі» (категорію в селекторі буде візуально вимкнено).
  useEffect(() => {
    const tags = mainMaterial?.tags || [];
    if (audience && (audience.forbidden_tags || []).some((t) => tags.includes(t))) {
      setAudienceId("adults");
    }
  }, [mainMaterialId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Авто-профіль: для ЦА з suggest=true підставляємо популярний профіль за
  // категорією + основною сировиною (саме обраним варіантом — форма/кісточка).
  // Користувач може його потім змінити.
  const mainVariantKey = mainMaterial
    ? `${mainMaterial.part}|${mainMaterial.form}|${mainMaterial.pit}`
    : "";
  useEffect(() => {
    if (!audience || !audience.suggest) return;
    let cancelled = false;
    api
      .suggestProfile({
        audience_id: audienceId,
        main_material_id: mainMaterialId,
        part: mainMaterial?.part ?? null,
        form: mainMaterial?.form ?? null,
        pit: mainMaterial?.pit ?? null,
      })
      .then((r) => {
        if (!cancelled) setDesired(r.characteristic_ids);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [audienceId, mainMaterialId, mainVariantKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Безалкогольні ЦА: лишаємо лише 0%-основу, дефолт — перша безалкогольна.
  useEffect(() => {
    if (!alcoholFree) return;
    const allowed = bases.filter((b) => NON_ALCOHOLIC_BASES.has(b.name));
    if (baseId && allowed.some((b) => b.id === baseId)) return;
    setBaseId(allowed[0]?.id ?? null);
  }, [alcoholFree, bases]); // eslint-disable-line react-hooks/exhaustive-deps

  const canSubmit = mainMaterial?.material_id && !loading;

  async function handleGenerate() {
    setError(null);
    setLoading(true);
    setResult(null);
    try {
      const payload = {
        main_material: {
          material_id: mainMaterial.material_id,
          part: mainMaterial.part,
          form: mainMaterial.form,
          pit: mainMaterial.pit,
        },
        additional_materials: additional
          .filter((a) => a && a.material_id)
          .map((a) => ({
            material_id: a.material_id,
            part: a.part,
            form: a.form,
            pit: a.pit,
          })),
        base_id: baseId,
        desired_characteristics: desired,
        audience_id: audienceId,
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
      <header className="mb-6 text-center">
        <img
          src={logo}
          alt="charkaLab"
          className="mx-auto w-full max-w-sm object-contain"
        />
        <p className="mt-3 text-stone-500">
          Генератор рецептів мацератів на основі ароматичних сполук
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <Section
          step={1}
          title="Цільова аудиторія"
          hint="Для кого напій. Деякі категорії жорстко виключають небезпечну сировину та лишають лише безалкогольну основу."
        >
          <AudienceSelector
            audiences={audiences}
            value={audienceId}
            onChange={setAudienceId}
            mainMaterialTags={mainMaterial?.tags ?? []}
          />
          {audience?.disclaimer && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {audience.disclaimer}
            </div>
          )}
        </Section>

        <Section
          step={2}
          title="Основна сировина"
          hint="Почніть вводити назву — підкаже по перших літерах."
        >
          <MaterialAutocomplete
            value={mainMaterial}
            onChange={setMainMaterial}
            forbiddenTags={forbiddenTags}
          />
        </Section>

        <Section
          step={3}
          title="Допоміжна сировина"
          hint="Необов'язково. До 10 рядків, кожен з формою та (за потреби) кісточкою."
        >
          <AdditionalMaterials
            rows={additional}
            onChange={setAdditional}
            forbiddenTags={forbiddenTags}
          />
        </Section>

        <Section step={4} title="Основа напою">
          <BaseSelector
            bases={bases}
            value={baseId}
            onChange={setBaseId}
            mainMaterialName={mainMaterial?.name ?? null}
            alcoholFree={alcoholFree}
          />
        </Section>

        <Section
          step={5}
          title="Бажаний профіль напою"
          hint={
            audience?.suggest
              ? "Профіль підібрано під аудиторію — змініть за смаком."
              : "Які характеристики має мати напій?"
          }
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
          className="rounded-xl bg-charka-600 px-6 py-3 text-base font-semibold text-white shadow hover:bg-charka-700 disabled:cursor-not-allowed disabled:opacity-40"
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
