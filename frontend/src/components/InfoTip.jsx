// Кружечок "i" з підказкою на ховер/фокус (доступно з клавіатури).
// side — з якого боку розкривається підказка відносно іконки;
// align — як вирівняти її по горизонталі, щоб не вилазила за екран
// (напр. праворуч від бейджів у верхньому правому куті картки).
const SIDE_CLASSES = {
  top: "bottom-full mb-2",
  bottom: "top-full mt-2",
};

const ALIGN_CLASSES = {
  center: "left-1/2 -translate-x-1/2",
  left: "left-0",
  right: "right-0",
};

export default function InfoTip({ text, side = "top", align = "center", className = "" }) {
  return (
    <span className={`group/tip relative inline-flex align-middle ${className}`}>
      <button
        type="button"
        aria-label="Пояснення"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-stone-300 bg-white text-[10px] font-bold not-italic normal-case leading-none tracking-normal text-stone-500 transition hover:border-charka-500 hover:text-charka-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-charka-400"
      >
        i
      </button>
      <span
        role="tooltip"
        className={
          "pointer-events-none absolute z-30 w-60 whitespace-pre-line rounded-lg border border-stone-700 bg-stone-800 p-2.5 text-left text-xs font-normal not-italic normal-case leading-relaxed tracking-normal text-white opacity-0 shadow-xl transition-opacity duration-150 group-hover/tip:opacity-100 group-focus-within/tip:opacity-100 " +
          `${SIDE_CLASSES[side]} ${ALIGN_CLASSES[align]}`
        }
      >
        {text}
      </span>
    </span>
  );
}
