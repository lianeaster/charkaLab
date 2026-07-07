import { SEASONS } from "../api";

// value: id сезону або null («Будь-який сезон» — без урахування сезонності)
export default function SeasonSelector({ value, onChange }) {
  const options = [{ id: null, label: "Будь-який сезон", emoji: "♾️" }, ...SEASONS];
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((s) => {
        const active = value === s.id;
        return (
          <button
            key={s.id ?? "any"}
            type="button"
            onClick={() => onChange(s.id)}
            className={
              "rounded-full border px-4 py-2 text-sm transition " +
              (active
                ? "border-charka-600 bg-charka-600 text-white"
                : "border-stone-300 bg-white text-stone-700 hover:border-charka-500")
            }
          >
            <span className="mr-1" aria-hidden>
              {s.emoji}
            </span>
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
