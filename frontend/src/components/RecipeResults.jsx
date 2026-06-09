import { PYRAMID_META, ROLE_LABELS, variantLabel } from "../api";

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

// Цільовий рівень бажаної ноти (узгоджено з TARGET_STRENGTH на бекенді)
const RADAR_TARGET = 0.8;
const RADAR_MAX_AXES = 11;

// Сумарний внесок кожної характеристики (аромат + смак) для варіанта
function mergedTotals(variant) {
  const totals = {};
  for (const p of [...variant.aroma_profile, ...variant.taste_profile]) {
    totals[p.name] = (totals[p.name] || 0) + p.score;
  }
  return totals;
}

// Спільний максимум по всіх варіантах, щоб радари мали однаковий масштаб
// (інакше пунктир «бажаного» плаває й варіанти стають непорівнянними).
function radarScaleMax(variants) {
  let m = RADAR_TARGET;
  for (const v of variants) {
    const t = mergedTotals(v);
    for (const k in t) m = Math.max(m, t[k]);
  }
  return m || 1;
}

function ProfileRadar({ variant, desired, scaleMax }) {
  const desiredList = desired || [];
  const totals = mergedTotals(variant);
  // Осі: бажані ноти + найсильніші присутні (щоб не було каші з 50 осей)
  const others = Object.keys(totals)
    .filter((n) => !desiredList.includes(n))
    .sort((a, b) => totals[b] - totals[a]);
  const slots = Math.max(0, RADAR_MAX_AXES - desiredList.length);
  const axes = [...desiredList, ...others.slice(0, slots)];
  if (axes.length < 3) return null; // радар має сенс від 3 осей

  const maxVal = scaleMax || Math.max(RADAR_TARGET, ...axes.map((a) => totals[a] || 0)) || 1;
  const size = 280;
  const cx = size / 2;
  const cy = size / 2;
  const R = 88;
  const n = axes.length;
  const angle = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const pt = (i, val) => {
    const r = R * Math.min(val / maxVal, 1.04);
    return [cx + r * Math.cos(angle(i)), cy + r * Math.sin(angle(i))];
  };
  const toPath = (pts) =>
    pts.map(([x, y], i) => (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1)).join(" ") + " Z";

  const achieved = axes.map((a, i) => pt(i, totals[a] || 0));
  const target = axes.map((a, i) => pt(i, desiredList.includes(a) ? RADAR_TARGET : 0));
  const rings = [0.25, 0.5, 0.75, 1];

  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-400">
        Профіль: бажаний vs досягнутий
      </h4>
      <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto w-full max-w-[300px]">
        {/* кільця-сітка */}
        {rings.map((f) => (
          <polygon
            key={f}
            points={axes
              .map((_, i) => {
                const [x, y] = pt(i, maxVal * f);
                return `${x.toFixed(1)},${y.toFixed(1)}`;
              })
              .join(" ")}
            fill="none"
            stroke="#e7e5e4"
            strokeWidth="1"
          />
        ))}
        {/* спиці + підписи */}
        {axes.map((a, i) => {
          const [ex, ey] = pt(i, maxVal);
          const [lx, ly] = (() => {
            const r = R + 14;
            return [cx + r * Math.cos(angle(i)), cy + r * Math.sin(angle(i))];
          })();
          const cos = Math.cos(angle(i));
          const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
          const isDesired = desiredList.includes(a);
          return (
            <g key={a}>
              <line x1={cx} y1={cy} x2={ex} y2={ey} stroke="#e7e5e4" strokeWidth="1" />
              <text
                x={lx}
                y={ly}
                fontSize="9"
                textAnchor={anchor}
                dominantBaseline="middle"
                fill={isDesired ? "#b45309" : "#a8a29e"}
                fontWeight={isDesired ? 600 : 400}
              >
                {a}
              </text>
            </g>
          );
        })}
        {/* бажаний (ціль) — пунктир */}
        <path d={toPath(target)} fill="none" stroke="#78716c" strokeWidth="1.5" strokeDasharray="4 3" />
        {/* досягнутий — заливка */}
        <path d={toPath(achieved)} fill="rgba(217,119,6,0.18)" stroke="#d97706" strokeWidth="2" />
        {achieved.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r="2.5" fill="#d97706" />
        ))}
      </svg>
      <div className="mt-1 flex justify-center gap-4 text-xs text-stone-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-3 rounded-sm bg-charka-500/40 ring-1 ring-charka-600" />
          досягнутий
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0 w-3 border-t-2 border-dashed border-stone-500" />
          бажаний
        </span>
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

const LAYER_STYLE = {
  top: "border-charka-200 bg-charka-50",
  heart: "border-wine-300 bg-wine-50",
  base: "border-stone-300 bg-stone-100",
};

function Pyramid({ pyramid }) {
  if (!pyramid || !pyramid.length) return null;
  const order = ["top", "heart", "base"];
  const sorted = [...pyramid].sort(
    (a, b) => order.indexOf(a.layer) - order.indexOf(b.layer)
  );
  return (
    <div className="mb-4 rounded-xl border border-stone-200 bg-cream/40 p-3">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-stone-400">
        Піраміда нот (у часі)
      </h4>
      <div className="flex flex-col gap-2">
        {sorted.map((layer) => {
          const meta = PYRAMID_META[layer.layer] || { label: layer.title, hint: "" };
          const top = layer.notes.slice(0, 6);
          return (
            <div
              key={layer.layer}
              className={"rounded-lg border px-3 py-2 " + (LAYER_STYLE[layer.layer] || "")}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-semibold text-stone-700">
                  {meta.label}
                </span>
                <span className="text-[11px] text-stone-400">{meta.hint}</span>
              </div>
              {top.length ? (
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {top.map((n) => (
                    <span
                      key={n.name}
                      className={
                        "rounded-full px-2 py-0.5 text-xs " +
                        (n.covered
                          ? "bg-charka-600 text-white"
                          : "bg-white/70 text-stone-600")
                      }
                    >
                      {n.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="mt-1 text-xs italic text-stone-400">порожньо</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const ROLE_CHIP = {
  suggested: "border-wine-200 bg-wine-50 text-wine-700",
  balance: "border-charka-200 bg-charka-50 text-charka-700",
  sweetener: "border-charka-200 bg-charka-50 text-charka-700",
  harmony: "border-stone-300 bg-white text-stone-600",
  base: "border-stone-400 bg-stone-100 text-stone-700",
};

function VariantCard({ variant, index, desired, radarMax }) {
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
              {m.role === "main"
                ? " · основа"
                : m.amount != null
                ? ` · ${Math.round(m.amount * 100)}%`
                : ""}
            </span>
          </span>
        ))}
      </div>

      <p className="mb-3 text-sm text-stone-600">{variant.explanation}</p>

      <Pyramid pyramid={variant.pyramid} />

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

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <ProfileRadar variant={variant} desired={desired} scaleMax={radarMax} />
        <div className="flex flex-col gap-4">
          <ProfileBars title="Аромат" items={variant.aroma_profile} />
          <ProfileBars title="Смак" items={variant.taste_profile} />
        </div>
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

function BaseInfluenceBanner({ influence }) {
  if (!influence) return null;
  const hasConflict = influence.conflicts?.length > 0;
  const hasSynergy = influence.synergy?.length > 0;
  if (!hasConflict && !hasSynergy && !influence.note) return null;

  return (
    <div className="rounded-2xl border border-charka-200 bg-charka-50/60 p-4">
      <div className="mb-1 flex items-center gap-2 font-semibold text-charka-700">
        <span aria-hidden>🍶</span>
        Вплив основи: {influence.name}
      </div>
      <p className="text-sm text-stone-600">{influence.note}</p>
      {influence.abv_hint && (
        <p className="mt-1 text-xs text-stone-400">{influence.abv_hint}</p>
      )}
      {hasConflict && (
        <p className="mt-2 text-sm text-amber-800">
          <span className="font-medium">Конфліктує з профілем:</span>{" "}
          {influence.conflicts.join(", ")} — ці ноти можуть бути пригнічені.
        </p>
      )}
      {hasSynergy && (
        <p className="mt-1 text-sm text-charka-700">
          <span className="font-medium">Підсилює:</span>{" "}
          {influence.synergy.join(", ")}
        </p>
      )}
    </div>
  );
}

function FeasibilityBanner({ feasibility }) {
  if (!feasibility || feasibility.status === "ok") return null;
  const impossible = feasibility.status === "impossible";
  const cls = impossible
    ? "border-red-300 bg-red-50 text-red-800"
    : "border-amber-300 bg-amber-50 text-amber-900";
  const title = impossible
    ? "Профіль неможливо гарантувати"
    : "Профіль не домінуватиме";
  return (
    <div className={`rounded-2xl border p-4 ${cls}`}>
      <div className="flex items-center gap-2 font-semibold">
        <span aria-hidden>{impossible ? "⛔" : "⚠️"}</span>
        {title}
      </div>
      <p className="mt-1 text-sm">{feasibility.message}</p>
      {feasibility.dominating?.length > 0 && (
        <p className="mt-1 text-sm">
          Перебивають: <span className="font-medium">{feasibility.dominating.join(", ")}</span>
        </p>
      )}
    </div>
  );
}

export default function RecipeResults({ result }) {
  if (!result) return null;
  const radarMax = radarScaleMax(result.variants);
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
      <BaseInfluenceBanner influence={result.base_influence} />
      <FeasibilityBanner feasibility={result.feasibility} />
      {result.variants.map((v, i) => (
        <VariantCard
          key={i}
          variant={v}
          index={i}
          desired={result.desired}
          radarMax={radarMax}
        />
      ))}
    </div>
  );
}
