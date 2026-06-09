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
  generate: (payload) =>
    request(`/recipes/generate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const FORM_LABELS = {
  fresh: "свіжа",
  dry: "суха",
  extract: "екстракт",
};

export const PIT_LABELS = {
  with: "з кісточкою",
  without: "без кісточки",
  na: "—",
};

export const ROLE_LABELS = {
  main: "основна",
  additional: "додаткова",
  suggested: "підібрана",
};
