import { TAG_LABELS } from "../api";

// Причина, чому категорія недоступна для обраної основної сировини.
function blockReason(audience, mainTags) {
  const hit = (audience.forbidden_tags || []).find((t) => mainTags.includes(t));
  if (!hit) return null;
  return TAG_LABELS[hit] || hit;
}

function Group({ title, items, value, onChange, mainTags }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-medium uppercase tracking-wide text-stone-400">
        {title}
      </span>
      <div className="flex flex-wrap gap-2">
        {items.map((a) => {
          const reason = blockReason(a, mainTags);
          const disabled = Boolean(reason);
          const active = value === a.id;
          return (
            <button
              key={a.id}
              type="button"
              disabled={disabled}
              onClick={() => onChange(a.id)}
              title={
                disabled
                  ? `Недоступно для обраної сировини: ${reason}`
                  : a.alcohol_free
                    ? "Лише безалкогольна основа"
                    : undefined
              }
              className={
                "rounded-full border px-4 py-2 text-sm transition " +
                (disabled
                  ? "cursor-not-allowed border-stone-200 bg-stone-100 text-stone-300 line-through"
                  : active
                    ? "border-charka-600 bg-charka-600 text-white"
                    : "border-stone-300 bg-white text-stone-700 hover:border-charka-500")
              }
            >
              {a.name}
              {a.alcohol_free && (
                <span className="ml-1 text-xs opacity-70">0%</span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function AudienceSelector({
  audiences,
  value,
  onChange,
  mainMaterialTags,
}) {
  const mainTags = mainMaterialTags || [];
  const adults = audiences.filter((a) => a.group === "adults");
  const special = audiences.filter((a) => a.group === "special");

  return (
    <div className="flex flex-col gap-4">
      <Group
        title="Дорослі"
        items={adults}
        value={value}
        onChange={onChange}
        mainTags={mainTags}
      />
      <Group
        title="Спеціальні категорії"
        items={special}
        value={value}
        onChange={onChange}
        mainTags={mainTags}
      />
    </div>
  );
}
