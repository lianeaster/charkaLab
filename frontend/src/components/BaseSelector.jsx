const DISTILLATE_KEY = "ароматний дистилят (основна сировина)";

export default function BaseSelector({ bases, value, onChange, mainMaterialName }) {
  return (
    <div className="flex flex-wrap gap-2">
      {bases.map((b) => {
        const isDistillate = b.name === DISTILLATE_KEY;
        const active = value === b.id;
        const label = isDistillate && mainMaterialName
          ? `дистилят з ${mainMaterialName}`
          : b.name;
        return (
          <button
            key={b.id}
            type="button"
            onClick={() => onChange(active ? null : b.id)}
            title={isDistillate ? "Ароматний спирт, отриманий дистиляцією з основної сировини" : undefined}
            className={
              "rounded-full border px-4 py-2 text-sm transition " +
              (active
                ? "border-charka-600 bg-charka-600 text-white"
                : "border-stone-300 bg-white text-stone-700 hover:border-charka-500")
            }
          >
            {label}
            {isDistillate && !mainMaterialName && (
              <span className="ml-1 text-xs opacity-60">(обеpіть сировину)</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
