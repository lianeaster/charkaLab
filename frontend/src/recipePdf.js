import { jsPDF } from "jspdf";
import { PYRAMID_META, ROLE_LABELS, variantLabel } from "./api";

// Кириличний шрифт для jsPDF (вбудовані шрифти кирилиці не мають).
// Тягнемо TTF із /fonts один раз і кешуємо у base64.
let fontsPromise = null;

function bufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

async function loadFonts() {
  if (!fontsPromise) {
    fontsPromise = (async () => {
      const [reg, bold] = await Promise.all([
        fetch("/fonts/DejaVuSans.ttf").then((r) => r.arrayBuffer()),
        fetch("/fonts/DejaVuSans-Bold.ttf").then((r) => r.arrayBuffer()),
      ]);
      return { reg: bufferToBase64(reg), bold: bufferToBase64(bold) };
    })().catch((e) => {
      fontsPromise = null; // дозволити повтор при невдачі
      throw e;
    });
  }
  return fontsPromise;
}

function registerFonts(doc, fonts) {
  doc.addFileToVFS("DejaVuSans.ttf", fonts.reg);
  doc.addFont("DejaVuSans.ttf", "DejaVu", "normal");
  doc.addFileToVFS("DejaVuSans-Bold.ttf", fonts.bold);
  doc.addFont("DejaVuSans-Bold.ttf", "DejaVu", "bold");
}

// Простий потоковий рендер тексту з переносами та розривом сторінок.
function makeWriter(doc) {
  const margin = 48;
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const maxW = pageW - margin * 2;
  let y = margin;

  function ensure(h) {
    if (y + h > pageH - margin) {
      doc.addPage();
      y = margin;
    }
  }

  function text(str, opts = {}) {
    const {
      size = 10,
      style = "normal",
      color = [60, 50, 45],
      indent = 0,
      gap = 4,
      lineH = 1.35,
    } = opts;
    doc.setFont("DejaVu", style);
    doc.setFontSize(size);
    doc.setTextColor(color[0], color[1], color[2]);
    const lines = doc.splitTextToSize(String(str), maxW - indent);
    const lh = size * lineH;
    for (const line of lines) {
      ensure(lh);
      doc.text(line, margin + indent, y);
      y += lh;
    }
    y += gap;
  }

  function heading(str) {
    y += 4;
    text(str, { size: 12, style: "bold", color: [140, 70, 20], gap: 5 });
  }

  function rule() {
    ensure(8);
    doc.setDrawColor(225, 220, 215);
    doc.setLineWidth(0.6);
    doc.line(margin, y, pageW - margin, y);
    y += 10;
  }

  return { text, heading, rule, get y() { return y; } };
}

function pct(score) {
  return `${Math.round((score || 0) * 100)}%`;
}

function materialLine(m) {
  const parts = [m.name];
  if (m.role !== "sweetener") {
    const vl = variantLabel(m);
    if (vl && vl !== "—") parts.push(vl);
  }
  parts.push(ROLE_LABELS[m.role] || m.role);
  if (m.role === "main") {
    parts.push("основа");
  } else if (m.amount != null) {
    parts.push(`${Math.round(m.amount * 100)}%`);
  }
  return parts.join(" · ");
}

function topNotes(items, n = 6) {
  return [...(items || [])]
    .sort((a, b) => b.score - a.score)
    .slice(0, n)
    .map((it) => `${it.name} (${it.score.toFixed(2)})${it.covered ? " ✓" : ""}`)
    .join(", ");
}

export async function downloadRecipePdf(result, variant, index = 0) {
  const fonts = await loadFonts();
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  registerFonts(doc, fonts);
  const w = makeWriter(doc);

  // Шапка
  w.text("charkaLab — рецепт мацерату", {
    size: 9,
    style: "bold",
    color: [168, 162, 158],
    gap: 2,
  });
  w.text(variant.title || `Варіант ${index + 1}`, {
    size: 18,
    style: "bold",
    color: [40, 30, 25],
    gap: 6,
  });
  w.text(
    `Збіг профілю: ${pct(variant.match_score)}    Баланс смаку: ${pct(
      variant.balance_score
    )}    Гармонія смаку: ${pct(variant.harmony_score)}`,
    { size: 10, color: [120, 110, 100], gap: 4 }
  );
  if (result.base) w.text(`Основа: ${result.base}`, { size: 10, gap: 2 });
  const profileNotes =
    variant.desired?.length ? variant.desired : result.desired;
  if (profileNotes?.length)
    w.text(`Бажаний профіль: ${profileNotes.join(", ")}`, {
      size: 10,
      gap: 2,
    });
  if (result.audience) {
    const af = result.audience.alcohol_free ? " (0% алкоголю)" : "";
    w.text(`Аудиторія: ${result.audience.name}${af}`, { size: 10, gap: 2 });
  }
  w.rule();

  // Склад
  w.heading("Склад");
  for (const m of variant.materials || []) {
    w.text(`•  ${materialLine(m)}`, { size: 10, indent: 6, gap: 2 });
  }

  if (variant.explanation) {
    w.text(variant.explanation, {
      size: 9.5,
      color: [110, 100, 92],
      gap: 4,
    });
  }

  // Піраміда нот
  if (variant.pyramid?.length) {
    w.heading("Піраміда нот (у часі)");
    const order = ["top", "heart", "base"];
    const sorted = [...variant.pyramid].sort(
      (a, b) => order.indexOf(a.layer) - order.indexOf(b.layer)
    );
    for (const layer of sorted) {
      const meta = PYRAMID_META[layer.layer] || { label: layer.title, hint: "" };
      const notes = (layer.notes || []).slice(0, 6).map((n) => n.name).join(", ");
      w.text(`${meta.label} — ${meta.hint}`, {
        size: 10,
        style: "bold",
        color: [90, 60, 30],
        gap: 1,
      });
      w.text(notes || "порожньо", { size: 10, indent: 6, gap: 4 });
    }
  }

  // Профілі
  w.heading("Аромат і смак (топ-ноти)");
  w.text(`Аромат: ${topNotes(variant.aroma_profile) || "—"}`, {
    size: 10,
    gap: 3,
  });
  w.text(`Смак: ${topNotes(variant.taste_profile) || "—"}`, {
    size: 10,
    gap: 3,
  });

  // Балансування
  if (variant.balance_notes?.length) {
    w.heading("Балансування");
    for (const note of variant.balance_notes) {
      w.text(`•  ${note}`, { size: 10, indent: 6, gap: 2 });
    }
  }

  // Гастрономічна гармонія (лише за наявності дисонансу)
  if (variant.harmony_score != null && variant.harmony_score < 0.85) {
    w.heading("Гастрономічна гармонія");
    const warn =
      variant.harmony_score < 0.6
        ? "Композиція збалансована за смаковими осями, але поєднання смаків дисонує — навряд чи буде смачною."
        : "Легкий дисонанс між ароматичними родинами — смак може вийти неоднозначним.";
    w.text(warn, { size: 9.5, color: [170, 70, 60], gap: 3 });
    for (const note of variant.harmony_notes || []) {
      w.text(`•  ${note}`, { size: 10, indent: 6, gap: 2 });
    }
  }

  // Слабкі / відсутні ноти
  if (variant.weak?.length) {
    w.text(`Слабко виражені: ${variant.weak.join(", ")}`, {
      size: 9.5,
      color: [150, 100, 30],
      gap: 2,
    });
  }
  if (variant.missing?.length) {
    w.text(`Не вистачає: ${variant.missing.join(", ")}`, {
      size: 9.5,
      color: [170, 70, 60],
      gap: 2,
    });
  }

  // Аромосполуки
  if (variant.compounds?.length) {
    w.heading(`Аромосполуки (${variant.compounds.length})`);
    for (const c of variant.compounds) {
      w.text(
        `•  ${c.compound} (${c.kind}) — ${(c.characteristics || []).join(", ")}`,
        { size: 9, color: [110, 100, 92], indent: 6, gap: 1 }
      );
    }
  }

  // Дисклеймер аудиторії
  if (result.audience?.disclaimer) {
    w.rule();
    w.text(result.audience.disclaimer, {
      size: 8.5,
      color: [150, 145, 140],
      gap: 2,
    });
  }

  // Підпис
  const date = new Date().toLocaleDateString("uk-UA");
  w.text(`Згенеровано charkaLab · ${date}`, {
    size: 8,
    color: [180, 175, 170],
    gap: 0,
  });

  const safe = (variant.title || "recipe")
    .replace(/[^\p{L}\p{N}]+/gu, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 50);
  doc.save(`charkaLab_${safe || "recipe"}.pdf`);
}
