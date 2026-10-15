import { useEffect, useState } from "react";

// Налаштування технологічної карти, спільні для всіх варіантів і для PDF:
// рівень («домашній» / «просунутий») і обладнання, яке є в користувача.
// Живуть у localStorage лише як зручність — без нього все працює з типовими.
const LEVEL_KEY = "charkalab.processLevel";
const EQUIPMENT_KEY = "charkalab.equipment";
const CHANGE_EVENT = "charkalab-process-prefs";

export const EQUIPMENT = [
  { key: "ultrasound", label: "Ультразвукова ванна" },
  { key: "vacuum", label: "Вакуум (камера чи кришки з насосом)" },
  { key: "sousvide", label: "Термостатна баня (sous-vide чи ванна з підігрівом)" },
  { key: "freezer", label: "Морозилка −18 °C" },
  { key: "enzymes", label: "Ферментні препарати" },
  { key: "still", label: "Перегінний куб із кошиком" },
  { key: "siphon", label: "Сифон із N₂O" },
];

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // приватний режим чи заблоковане сховище — працюємо без запам'ятовування
  }
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function readProcessPrefs() {
  return {
    level: read(LEVEL_KEY, "home"),
    equipment: read(EQUIPMENT_KEY, []),
  };
}

// Чи є все обладнання для способу: "ultrasound+sousvide" — ультразвукова
// ванна з підігрівом, тобто потрібні обидва; "none" — доступний завжди.
export function hasEquipment(option, equipment) {
  return (
    option.equipment === "none" ||
    option.equipment.split("+").every((k) => equipment.includes(k))
  );
}

// Перший спосіб мацерації фракції, для якого є обладнання.
export function pickOption(fraction, equipment) {
  return (
    fraction.options.find((o) => hasEquipment(o, equipment)) ||
    fraction.options[fraction.options.length - 1]
  );
}

export function useProcessPrefs() {
  const [prefs, setPrefs] = useState(readProcessPrefs);
  useEffect(() => {
    const sync = () => setPrefs(readProcessPrefs());
    window.addEventListener(CHANGE_EVENT, sync);
    return () => window.removeEventListener(CHANGE_EVENT, sync);
  }, []);
  return {
    ...prefs,
    setLevel: (level) => write(LEVEL_KEY, level),
    toggleEquipment: (key) =>
      write(
        EQUIPMENT_KEY,
        prefs.equipment.includes(key)
          ? prefs.equipment.filter((k) => k !== key)
          : [...prefs.equipment, key]
      ),
  };
}
