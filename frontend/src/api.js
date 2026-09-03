const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  suggestMaterials: (q) =>
    request(`/materials/suggest?q=${encodeURIComponent(q)}`),
  materialForms: (id) => request(`/materials/${id}/forms`),
  characteristics: () => request(`/characteristics`),
  bases: () => request(`/bases`),
  audiences: () => request(`/audiences`),
  suggestProfile: (payload) =>
    request(`/audiences/suggest-profile`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  generate: (payload) =>
    request(`/recipes/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  recompute: (payload) =>
    request(`/recipes/recompute`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  surprise: (payload) =>
    request(`/recipes/surprise`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

// Назви основ без алкоголю (0% ABV) — лише вони доступні безалкогольним ЦА.
export const NON_ALCOHOLIC_BASES = new Set([
  "сік (фруктовий)",
  "мінеральна вода газована",
]);

// Людські підписи тегів-протипоказань (для пояснення, чому ЦА вимкнено).
export const TAG_LABELS = {
  pregnancy_unsafe: "не для вагітних/годуючих",
  kids_unsafe: "не для дітей",
  caffeine: "містить кофеїн",
};

// Сезони (співпадають з backend/app/seasons.py). null — «не враховувати».
export const SEASONS = [
  { id: "spring", label: "Весна", emoji: "🌸" },
  { id: "summer", label: "Літо", emoji: "☀️" },
  { id: "autumn", label: "Осінь", emoji: "🍂" },
  { id: "winter", label: "Зима", emoji: "❄️" },
];

// Поточний сезон за датою (північна півкуля) — дефолтний вибір.
export function currentSeason(date = new Date()) {
  const m = date.getMonth() + 1;
  if (m >= 3 && m <= 5) return "spring";
  if (m >= 6 && m <= 8) return "summer";
  if (m >= 9 && m <= 11) return "autumn";
  return "winter";
}

export const FORM_LABELS = {
  fresh: "свіжа",
  dry: "суха",
  extract: "екстракт",
  oil: "олія",
  juice: "сік",
  na: "—",
};

export const PART_LABELS = {
  whole: "",
  flower: "квіти",
  zest: "цедра",
  fruit: "плід",
  berry: "ягоди",
  leaf: "листя",
  root: "корінь",
  bark: "кора",
  seed: "насіння",
  herb: "трава",
  needle: "хвоя",
  rhizome: "кореневище",
  resin: "смола",
  bulb: "цибулина",
  stalk: "стебло",
  peel: "шкірка",
};

export const PIT_LABELS = {
  with: "з кісточкою",
  without: "без кісточки",
  na: "—",
};

// Людська назва варіанту сировини з частини/форми/кісточки
export function variantLabel(o) {
  if (!o) return "";
  const parts = [];
  const partLabel = PART_LABELS[o.part] ?? o.part;
  if (partLabel) parts.push(partLabel);
  const formLabel = FORM_LABELS[o.form] || o.form;
  if (o.form && o.form !== "na") parts.push(formLabel);
  if (o.pit && o.pit !== "na") parts.push(PIT_LABELS[o.pit] || o.pit);
  return parts.join(" · ") || "—";
}

export const ROLE_LABELS = {
  main: "основна",
  additional: "додаткова",
  suggested: "підібрана",
  balance: "для балансу",
  harmony: "для гармонії",
  reinforce: "підсилює ноту",
  complexity: "для багатогранності",
  sweetener: "для солодкості",
  base: "для післясмаку",
};

export const PYRAMID_META = {
  top: { label: "Верхні ноти", hint: "яскравий старт, швидко зникають" },
  heart: { label: "Серце", hint: "ядро напою — основна сировина" },
  base: { label: "База", hint: "глибокий стійкий післясмак" },
};
