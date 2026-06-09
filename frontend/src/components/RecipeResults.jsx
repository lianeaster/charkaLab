import { ROLE_LABELS, variantLabel } from "../api";

function ProfileBars({ title, items }) {
  if (!items.length) return null;
  const max = Math.max(...items.map((i) => i.score), 1);
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-400">
        {title}
      </h4>
      <div className="flex flex-col gap-1">
        {items.map((it) => (
          <div key={it.name} className="flex items-center gap-2 text-sm">
            <span
              className={
                "w-28 shrink-0 " +
                (it.covered ? "font-medium text-charka-700" : "text-stone-500")
              }
            >
              {it.name}
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded bg-stone-100">
              <div
                className={it.covered ? "h-full bg-charka-500" : "h-full bg-stone-300"}
                style={{ width: `${(it.score / max) * 100}%` }}
              />
            </div>
            <span className="w-10 shrink-0 text-right text-xs text-stone-400">
              {it.score.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ScoreBadge({ score }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "bg-charka-600" : pct >= 50 ? "bg-charka-400" : "bg-stone-400";
  return (
    <span className={`rounded-full px-3 py-1 text-sm font-semibold text-white ${color}`}>
      {pct}% збіг
    </span>
  );
}

function BalanceBadge({ score }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 85 ? "bg-wine-500" : pct >= 60 ? "bg-wine-200 text-wine-700" : "bg-stone-300 text-stone-700";
  const textColor = pct >= 85 ? "text-white" : "";
  return (
    <span className={`rounded-full px-3 py-1 text-sm font-semibold ${color} ${textColor}`}>
      {pct}% баланс
    </span>
  );
}

const ROLE_CHIP = {
  suggested: "border-wine-200 bg-wine-50 text-wine-700",
  balance: "border-charka-200 bg-charka-50 text-charka-700",
  sweetener: "border-charka-200 bg-charka-50 text-charka-700",
  harmony: "border-stone-300 bg-white text-stone-600",
};

function VariantCard({ variant, index }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <span className="text-xs font-medium text-charka-600">
            Варіант {index + 1}
          </span>
          <h3 className="text-lg font-semibold text-stone-800">{variant.title}</h3>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <ScoreBadge score={variant.match_score} />
          <BalanceBadge score={variant.balance_score} />
        </div>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {variant.materials.map((m, i) => (
          <span
            key={i}
            className={
              "rounded-lg border px-3 py-1.5 text-sm " +
              (ROLE_CHIP[m.role] || "border-stone-200 bg-stone-50 text-stone-700")
            }
          >
            <span className="font-medium">{m.name}</span>
            <span className="text-xs text-stone-500">
              {m.role !== "sweetener" ? ` · ${variantLabel(m)}` : ""}
              {" · "}
              {ROLE_LABELS[m.role] || m.role}
            </span>
          </span>
        ))}
      </div>

      <p className="mb-3 text-sm text-stone-600">{variant.explanation}</p>

      {variant.balance_notes && variant.balance_notes.length > 0 && (
        <div className="mb-4 rounded-lg border border-charka-100 bg-charka-50/60 p-3">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-charka-700">
            Балансування
          </h4>
          <ul className="flex flex-col gap-0.5 text-sm text-stone-600">
            {variant.balance_notes.map((n, i) => (
              <li key={i}>• {n}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-4 grid gap-4 sm:grid-cols-2">
        <ProfileBars title="Аромат" items={variant.aroma_profile} />
        <ProfileBars title="Смак" items={variant.taste_profile} />
      </div>

      <details className="text-sm">
        <summary className="cursor-pointer text-stone-500 hover:text-stone-700">
          Аромосполуки ({variant.compounds.length})
        </summary>
        <ul className="mt-2 flex flex-col gap-1">
          {variant.compounds.map((c) => (
            <li key={c.compound} className="text-stone-600">
              <span className="font-medium text-stone-800">{c.compound}</span>
              <span className="text-xs text-stone-400"> ({c.kind})</span>
              {" — "}
              {c.characteristics.join(", ")}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

export default function RecipeResults({ result }) {
  if (!result) return null;
  return (
    <div className="flex flex-col gap-4">
      <div className="text-sm text-stone-500">
        Основа: <span className="font-medium text-stone-700">{result.base || "—"}</span>
        {" · "}
        Бажаний профіль:{" "}
        <span className="font-medium text-stone-700">
          {result.desired.join(", ") || "не задано"}
        </span>
      </div>
      {result.variants.map((v, i) => (
        <VariantCard key={i} variant={v} index={i} />
      ))}
    </div>
  );
}
