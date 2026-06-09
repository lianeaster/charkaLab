export default function ProfileSelector({ characteristics, selected, onChange }) {
  function toggle(id) {
    if (selected.includes(id)) {
      onChange(selected.filter((x) => x !== id));
    } else {
      onChange([...selected, id]);
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {characteristics.map((c) => {
        const active = selected.includes(c.id);
        return (
          <button
            key={c.id}
            type="button"
            onClick={() => toggle(c.id)}
            className={
              "rounded-full border px-3 py-1.5 text-sm transition " +
              (active
                ? "border-wine-600 bg-wine-600 text-white"
                : "border-stone-300 bg-white text-stone-700 hover:border-wine-500")
            }
          >
            {c.name}
          </button>
        );
      })}
    </div>
  );
}
