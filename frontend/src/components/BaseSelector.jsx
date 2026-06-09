export default function BaseSelector({ bases, value, onChange }) {
  return (
    <div className="flex flex-wrap gap-2">
      {bases.map((b) => {
        const active = value === b.id;
        return (
          <button
            key={b.id}
            type="button"
            onClick={() => onChange(active ? null : b.id)}
            className={
              "rounded-full border px-4 py-2 text-sm transition " +
              (active
                ? "border-charka-600 bg-charka-600 text-white"
                : "border-stone-300 bg-white text-stone-700 hover:border-charka-500")
            }
          >
            {b.name}
          </button>
        );
      })}
    </div>
  );
}
