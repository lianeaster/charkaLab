"""Звірка нашої бази сполук із довідниками the.in.ua.

Довідники ref.the.in.ua («Ароматичні сполуки», «Фрукти, ягоди та горіхи»,
«Спеції та трави») для кожної сировини наводять ключові аромосполуки з
рецензованої статті (GC-O, AEDA, OAV або склад ефірної олії) і саму статтю.
Скрипт порівнює їх із нашим seed і друкує Markdown-звіт розбіжностей:

- ключові сполуки зі статті, яких у нашому складі сировини немає;
- наші сполуки, яких у нашій базі немає взагалі (кандидати на додавання);
- дублікати в нашій базі (одна молекула під двома назвами).

Сполуки зіставляються за CAS (seed.COMPOUND_CAS), а де в нас збірний клас
(«фруктові естери», «лактони») — за CLASS_MAP нижче. Це звірка напрямку, а не
кількостей: стаття каже, ЩО пахне в сировині, а не скільки його.

Запуск (з каталогу backend):
    .venv/bin/python -m scripts.compare_reference > report.md
"""

from __future__ import annotations

import json
import sys
import urllib.request
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app.seed import COMPOUND_CAS, MATERIAL_PART, SEED_DATA

REF_BASE = "https://ref.the.in.ua/refs/raw/"
REFS = ("aroma-compounds", "fruits-berries", "spices")

# Їхні сполуки, які в нас представлені збірним класом або іншим ізомером.
# Ключ — id запису в їхньому довіднику, значення — назва нашої сполуки.
CLASS_MAP: Dict[str, str] = {
    # складні ефіри → «фруктові естери»
    **{cid: "фруктові естери" for cid in (
        "ethyl_butanoate", "ethyl_2_methylbutanoate", "ethyl_hexanoate",
        "ethyl_decanoate", "ethyl_isobutyrate", "ethyl_isovalerate",
        "ethyl_octanoate", "methyl_butanoate", "methyl_2_methylbutanoate",
        "methyl_isobutyrate", "butyl_acetate", "methylbutyl_acetate",
        "hexyl_acetate", "pear_ester",
    )},
    # γ/δ-лактони → «лактони»
    **{cid: "лактони" for cid in (
        "gamma_decalactone", "gamma_dodecalactone", "gamma_nonalactone",
        "delta_decalactone", "dodecenolide", "wine_lactone",
    )},
    # дамаскенон — «рожевий кетон» парфумерії
    "damascenone": "Рожеві кетони",
    "beta_ionone": "ірон",  # фіалковий тон, як у іронів
    # зелені C6-альдегіди → наш «гексенал»
    "hexanal": "гексенал",
    "z_3_hexenal": "гексенал",
    # ізомери, які в нас одною сполукою
    "carvone": "карвон",
    "alpha_thujone": "туйон",
    "beta_thujone": "туйон",
    "gamma_irone": "ірон",
    "alpha_selinene": "селінен",
    "alpha_farnesene": "Фарнезен",
    "alpha_turmerone": "ар-Турмерон",
    "beta_turmerone": "ар-Турмерон",
    "geranial": "цитраль",
    "neral": "цитраль",
    "chamazulene": "Азулен",
    "acetic_acid": "органічні кислоти",
    "phenylethyl_itc": "Ізотіоціанати",
}

# Їхній запис сировини → (наша сировина, частина, форма). Частина None —
# будь-яка (у нас "whole" перепризначається через MATERIAL_PART).
MATERIAL_MAP: Dict[str, Tuple[str, Optional[str], str]] = {
    "apricot-default": ("абрикос", None, "fresh"),
    "gooseberry-default": ("аґрус", None, "fresh"),
    "quince-default": ("айва", None, "fresh"),
    "pineapple-default": ("ананас", None, "fresh"),
    "orange-zest": ("апельсин", "zest", "fresh"),
    "elderberry-default": ("бузина чорна", "berry", "fresh"),
    "grape-white": ("виноград", None, "fresh"),
    "grape-muscat": ("виноград", None, "fresh"),
    "grape-red": ("виноград", None, "fresh"),
    "cherry-sour": ("вишня", "fruit", "fresh"),
    "cherry-sweet": ("черешня", None, "fresh"),
    "aronia-aronia": ("чорноплідна горобина", None, "fresh"),
    "pomegranate-default": ("гранат", None, "fresh"),
    "grapefruit-default": ("грейпфрут", "fruit", "juice"),
    "pear-conference": ("груша", None, "fresh"),
    "cranberry-default": ("журавлина", None, "fresh"),
    "fig-default": ("інжир", None, "fresh"),
    "kiwi-default": ("ківі", None, "fresh"),
    "lime-default": ("лайм", "zest", "fresh"),
    "lemon-zest": ("лимон", "zest", "fresh"),
    "blueberry-default": ("чорниця", None, "fresh"),
    "raspberry-red": ("малина", "berry", "fresh"),
    "mandarin-default": ("мандарин", "zest", "fresh"),
    "nectarine-default": ("нектарин", None, "fresh"),
    "sea_buckthorn-default": ("обліпина", None, "fresh"),
    "blackberry-default": ("ожина", None, "fresh"),
    "peach-default": ("персик", None, "fresh"),
    "strawberry-default": ("полуниця", None, "fresh"),
    "plum-hungarian": ("слива", None, "fresh"),
    "black_currant-black": ("чорна смородина", "berry", "fresh"),
    "persimmon-default": ("хурма", None, "fresh"),
    "rosehip-default": ("шипшина", None, "fresh"),
    "apple-sour": ("яблуко зелене", None, "fresh"),
    "apple-sweet": ("яблуко", None, "fresh"),
    "calamus": ("аїр болотний", None, "dry"),
    "anise": ("аніс", None, "dry"),
    "star_anise": ("бадьян", None, "dry"),
    "basil_dried": ("базилік", None, "dry"),
    "elderflower": ("бузина чорна", "flower", "dry"),
    "vanilla": ("ваніль", None, "dry"),
    "clove": ("гвоздика", None, "dry"),
    "mustard_seed": ("гірчиця", None, "dry"),
    "yarrow": ("деревій", None, "dry"),
    "angelica_root": ("дягель", "root", "dry"),
    "tarragon": ("естрагон", None, "fresh"),
    "st_johns_wort": ("звіробій", None, "dry"),
    "cumin": ("кмин", None, "dry"),
    "sweetgrass": ("зубровка", None, "dry"),
    "ginger": ("імбир", None, "fresh"),
    "orris_root": ("ірис (фіалковий корінь)", None, "dry"),
    "cardamom": ("кардамон", None, "dry"),
    "caraway": ("тмин", None, "dry"),
    "cinnamon": ("кориця цейлонська", None, "dry"),
    "coriander_seed": ("коріандр", "seed", "dry"),
    "dill_seed": ("кріп", "seed", "dry"),
    "turmeric": ("куркума", None, "dry"),
    "lavender": ("лаванда", None, "dry"),
    "bay_leaf": ("лавровий лист", None, "dry"),
    "linden_flower": ("липа", None, "dry"),
    "peppermint": ("м'ята перечна", None, "dry"),
    "oregano": ("душиця (орегано)", None, "dry"),
    "lemon_balm": ("меліса", None, "dry"),
    "nutmeg": ("мускатний горіх", None, "dry"),
    "paprika": ("паприка", None, "dry"),
    "allspice": ("духмяний перець", None, "dry"),
    "chili": ("червоний гострий перець", None, "fresh"),
    "black_pepper": ("чорний перець", None, "dry"),
    "wormwood_leaf": ("полин", None, "dry"),
    "chamomile": ("ромашка", None, "dry"),
    "licorice_root": ("солодка (лакриця)", None, "dry"),
    "fennel_seed": ("фенхель", "seed", "dry"),
    "horseradish": ("хрін", None, "fresh"),
    "thyme": ("чебрець (тим'ян)", None, "dry"),
    "sage": ("шавлія", None, "dry"),
    "juniper": ("ялівець", None, "dry"),
    "walnut-green": ("волоський горіх", "fruit", "fresh"),
    "walnut-ripe": ("волоський горіх", "seed", "dry"),
    "hazelnut-kernel": ("фундук", "seed", "dry"),
    "almond-kernel": ("мигдаль", "seed", "dry"),
    "mugwort": ("полин звичайний", None, "dry"),
}


def fetch(ref: str) -> dict:
    with urllib.request.urlopen(REF_BASE + ref + ".json", timeout=30) as resp:
        return json.load(resp)


def our_variant(mat: dict, part: Optional[str], form: str) -> Dict[str, float]:
    """Склад нашої сировини для частини/форми: {сполука: інтенсивність}."""
    default_part = MATERIAL_PART.get(mat["name"])
    out: Dict[str, float] = {}
    for link in mat["compounds"]:
        p = link.get("part", "whole")
        if p == "whole" and default_part:
            p = default_part
        if link.get("form", "fresh") != form or (part and p != part):
            continue
        out[link["compound"]] = max(out.get(link["compound"], 0.0), link["intensity"])
    return out


def main() -> None:
    compounds = {c["id"]: c for c in fetch("aroma-compounds")["items"]}
    their_materials = {
        i["id"]: {**i, "_ref": ref}
        for ref in ("fruits-berries", "spices")
        for i in fetch(ref)["items"]
    }

    by_cas = {cas: name for name, cas in COMPOUND_CAS.items()}
    our_kind = {c["name"]: c["kind"] for c in SEED_DATA["compounds"]}
    our_materials = {m["name"]: m for m in SEED_DATA["materials"]}

    def to_ours(cid: str) -> Optional[str]:
        """Наша сполука для їхньої: спершу за CAS, потім за CLASS_MAP."""
        cas = compounds.get(cid, {}).get("cas")
        return by_cas.get(cas) or CLASS_MAP.get(cid)

    w = sys.stdout.write
    w("# Звірка складу сировини з першоджерелами (the.in.ua)\n\n")
    w("Згенеровано `scripts/compare_reference.py`.\n\n")

    # --- 1. дублікати CAS у нас ---
    dup: Dict[str, List[str]] = defaultdict(list)
    for name, cas in COMPOUND_CAS.items():
        dup[cas].append(name)
    dups = {cas: names for cas, names in dup.items() if len(names) > 1}
    w("## Дублікати в нашій базі\n\n")
    if dups:
        for cas, names in sorted(dups.items()):
            w(f"- CAS {cas}: {' = '.join(names)}\n")
    else:
        w("Немає.\n")

    # --- 2. розбіжності складу ---
    missing_compounds: Dict[str, List[str]] = defaultdict(list)
    rows = []
    for tid, (our_name, part, form) in MATERIAL_MAP.items():
        item = their_materials.get(tid)
        mat = our_materials.get(our_name)
        if item is None or mat is None:
            rows.append((tid, our_name, None, None, None, None))
            continue
        keys = item.get("aroma_keys") or []
        if not keys:
            continue
        variant = our_variant(mat, part, form) or our_variant(mat, part, "dry" if form == "fresh" else "fresh")
        present, absent_here, absent_db = [], [], []
        for cid in keys:
            name = to_ours(cid)
            label = compounds[cid]["name"] if cid in compounds else cid
            if name is None:
                absent_db.append(label)
                missing_compounds[cid].append(item["name"])
            elif name in variant:
                present.append(f"{label} → {name} ({variant[name]:g})")
            else:
                absent_here.append(f"{label} → {name}")
        # наші сильні ароматні сполуки, яких стаття не називає ключовими
        key_ours = {to_ours(cid) for cid in keys}
        extra = sorted(
            (f"{n} ({i:g})" for n, i in variant.items()
             if i >= 0.6 and our_kind.get(n) != "taste" and n not in key_ours),
        )
        rows.append((item, our_name, present, absent_here, absent_db, extra))

    w("\n## Підсумок\n\n")
    w("| Довідник | Сировини | Ключових сполук | Є в нашому складі |\n|---|---|---|---|\n")
    for ref, title in (("fruits-berries", "Фрукти та ягоди"), ("spices", "Спеції та трави")):
        sel = [r for r in rows if r[2] is not None and r[0]["_ref"] == ref]
        hit = sum(len(r[2]) for r in sel)
        total = sum(len(r[2]) + len(r[3]) + len(r[4]) for r in sel)
        w(f"| {title} | {len(sel)} | {total} | {hit} ({100 * hit // max(1, total)}%) |\n")

    w("\n## Склад сировини проти першоджерела\n\n")
    w("Рахунок «збіг» — скільки ключових сполук зі статті є в нашому складі.\n\n")
    rows.sort(key=lambda r: (len(r[2]) / max(1, len(r[2]) + len(r[3]) + len(r[4])))
              if r[2] is not None else -1)
    for item, our_name, present, absent_here, absent_db, extra in rows:
        if present is None:
            w(f"### {item} → {our_name}: немає пари\n\n")
            continue
        total = len(present) + len(absent_here) + len(absent_db)
        w(f"### {item['name']} → «{our_name}» — збіг {len(present)}/{total}\n\n")
        w(f"Джерело: {item.get('aroma_src', '—')}\n\n")
        if present:
            w(f"- ✅ є: {', '.join(present)}\n")
        if absent_here:
            w(f"- ⚠️ є в базі, але не в цій сировині: {', '.join(absent_here)}\n")
        if absent_db:
            w(f"- ❌ немає в базі: {', '.join(absent_db)}\n")
        if extra:
            w(f"- ❔ наші сильні ноти, яких стаття не називає ключовими: {', '.join(extra)}\n")
        w("\n")

    w("## Сполуки, яких у нас немає, за частотою\n\n")
    for cid, mats in sorted(missing_compounds.items(), key=lambda kv: -len(kv[1])):
        c = compounds.get(cid, {})
        w(f"- **{c.get('name', cid)}** ({c.get('en', '')}, CAS {c.get('cas') or '—'}, "
          f"запах: {c.get('note') or '—'}) — {len(mats)}: {', '.join(mats)}\n")


if __name__ == "__main__":
    main()
