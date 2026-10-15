import InfoTip from "./InfoTip";
import { EQUIPMENT, hasEquipment, pickOption, useProcessPrefs } from "../processPrefs";

const PROCESS_HINT =
  "Як готувати саме цей склад. Час задається класом сировини: плодам — тижні, прянощам — дні, свіжій зелені — години. Дома все настоюється в одній банці, але ступінчасто: довге закладається першим, коротке — пізніше, щоб усе закінчило разом. Цифри — орієнтири для домашніх методів: пробуйте з указаного дня й знімайте, коли смак вас влаштовує.";

const LAB_HINT =
  "Кожен клас сировини — окрема фракція зі своїм співвідношенням, міцністю й режимом; потім фракції змішуються пробним купажем. Позначте обладнання, яке у вас є, — для кожної фракції буде показано найкращий доступний спосіб. Режими апаратних методів точні: їх задає апарат.";

function SectionTitle({ children }) {
  return (
    <h5 className="mb-1 text-xs font-semibold uppercase tracking-wide text-stone-500">
      {children}
    </h5>
  );
}

function Steps({ steps }) {
  return (
    <ul className="flex flex-col gap-0.5 text-stone-700">
      {steps.map((s, i) => (
        <li key={i}>• {s}</li>
      ))}
    </ul>
  );
}

function Cautions({ items }) {
  if (!items?.length) return null;
  return (
    <ul className="flex flex-col gap-0.5 rounded-md border border-amber-300 bg-amber-50 p-2 text-amber-800">
      {items.map((c, i) => (
        <li key={i}>⚠️ {c}</li>
      ))}
    </ul>
  );
}

function Basis({ items }) {
  if (!items?.length) return null;
  return (
    <p className="text-xs text-stone-400">
      На чому ґрунтуються орієнтири: {items.join("; ")}.
    </p>
  );
}

function HomeView({ process }) {
  return (
    <>
      <div>
        {process.temperature && (
          <p className="text-stone-700">
            <span className="font-medium">Режим:</span> {process.temperature}
          </p>
        )}
        {process.method_note && (
          <p className="mt-0.5 text-stone-500">{process.method_note}</p>
        )}
      </div>

      {process.schedule?.length > 0 && (
        <div>
          <SectionTitle>Графік закладання</SectionTitle>
          <ul className="flex flex-col gap-1">
            {process.schedule.map((t, i) => (
              <li key={i} className="text-stone-700">
                <span className="font-medium">{t.name}</span>
                <span className="text-stone-500"> · {t.class_title}</span>
                {" — "}
                {t.start}, {t.duration}
                {t.taste_from ? (
                  <span className="text-stone-500"> ({t.taste_from})</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {process.stages?.map((stage) =>
        stage.steps?.length ? (
          <div key={stage.key}>
            <SectionTitle>{stage.title}</SectionTitle>
            <Steps steps={stage.steps} />
          </div>
        ) : null
      )}

      <Cautions items={process.cautions} />
      <Basis items={process.basis} />
    </>
  );
}

function EquipmentPicker({ equipment, toggle }) {
  return (
    <div>
      <SectionTitle>Моє обладнання</SectionTitle>
      <p className="mb-1.5 text-xs text-stone-500">
        Ультразвукова ванна з підігрівом — позначте і ванну, і термостатну баню.
      </p>
      <div className="flex flex-wrap gap-1.5">
        {EQUIPMENT.map((e) => {
          const on = equipment.includes(e.key);
          return (
            <button
              key={e.key}
              type="button"
              onClick={() => toggle(e.key)}
              aria-pressed={on}
              className={
                "rounded-full border px-2.5 py-0.5 text-xs transition " +
                (on
                  ? "border-emerald-500 bg-emerald-600 text-white"
                  : "border-stone-300 bg-white text-stone-600 hover:border-emerald-400")
              }
            >
              {on ? "✓ " : ""}
              {e.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Fraction({ fraction, equipment }) {
  const chosen = pickOption(fraction, equipment);
  const pre = fraction.pretreatments.filter((p) => equipment.includes(p.equipment));
  const others = fraction.options.filter(
    (o) => o !== chosen && o.equipment !== "none" && hasEquipment(o, equipment)
  );
  return (
    <div className="rounded-md border border-emerald-200 bg-white p-2.5">
      <p className="font-medium text-stone-800">{fraction.title}</p>
      <p className="text-stone-600">{fraction.ingredients.join(", ")}</p>
      <p className="mb-1.5 text-xs text-stone-500">
        Сировина : спирт — {fraction.ratio} · спирт {fraction.abv}
      </p>
      {pre.map((p) => (
        <div key={p.equipment} className="mb-1.5">
          <p className="text-xs font-semibold text-stone-600">Спершу: {p.title}</p>
          <Steps steps={p.steps} />
        </div>
      ))}
      <p className="text-xs font-semibold text-emerald-800">{chosen.title}</p>
      <Steps steps={chosen.steps} />
      {others.length > 0 && (
        <p className="mt-1 text-xs text-stone-500">
          Також можна: {others.map((o) => o.title.toLowerCase()).join(", ")}.
        </p>
      )}
    </div>
  );
}

function LabView({ lab, equipment, toggle }) {
  return (
    <>
      <EquipmentPicker equipment={equipment} toggle={toggle} />
      <div className="flex flex-col gap-2">
        {lab.fractions.map((f) => (
          <Fraction key={f.key} fraction={f} equipment={equipment} />
        ))}
      </div>
      {lab.blend?.length > 1 && (
        <div>
          <SectionTitle>Пробний купаж</SectionTitle>
          <ul className="flex flex-col gap-0.5 text-stone-700">
            {lab.blend.map((b, i) => (
              <li key={i}>
                <span className="font-medium">{b.fraction}</span> — {b.target}
                {b.start ? <span className="text-stone-500"> ({b.start})</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      {lab.steps?.length > 0 && (
        <div>
          <SectionTitle>Зняття й купаж</SectionTitle>
          <Steps steps={lab.steps} />
        </div>
      )}
      <Cautions items={lab.cautions} />
      <Basis items={lab.basis} />
    </>
  );
}

// Технологічна карта варіанта: домашній рівень (одна банка, орієнтири) і
// просунутий (фракції, апаратні методи під наявне обладнання, пробний купаж).
export default function ProcessCard({ process, defaultOpen = false }) {
  const { level, equipment, setLevel, toggleEquipment } = useProcessPrefs();
  if (!process) return null;
  const lab = process.lab;
  const showLab = level === "lab" && lab;
  return (
    <details
      className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50/50 p-3"
      open={defaultOpen}
    >
      <summary className="flex cursor-pointer flex-wrap items-center gap-x-2 gap-y-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-emerald-800">
          Технологія приготування
        </span>
        <span className="text-sm text-stone-700">
          {showLab
            ? `фракційна мацерація · ${lab.fractions.length} фракц.`
            : `${process.method}${process.total_time ? ` · ${process.total_time}` : ""}`}
        </span>
        <InfoTip align="left" text={showLab ? LAB_HINT : PROCESS_HINT} />
      </summary>

      <div className="mt-3 flex flex-col gap-3 text-sm">
        {lab && (
          <div className="inline-flex w-fit rounded-full border border-emerald-300 bg-white p-0.5 text-xs">
            {[
              ["home", "Домашній"],
              ["lab", "Просунутий"],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setLevel(key)}
                aria-pressed={level === key}
                className={
                  "rounded-full px-3 py-0.5 transition " +
                  ((key === "lab") === Boolean(showLab)
                    ? "bg-emerald-600 text-white"
                    : "text-stone-600 hover:text-emerald-700")
                }
              >
                {label}
              </button>
            ))}
          </div>
        )}
        {showLab ? (
          <LabView lab={lab} equipment={equipment} toggle={toggleEquipment} />
        ) : (
          <HomeView process={process} />
        )}
      </div>
    </details>
  );
}
