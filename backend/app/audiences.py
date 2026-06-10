"""Цільова аудиторія напою.

Дві групи сегментів:
- adults — «дорослі» (нейтральний дефолт без авто-профілю) + стать (жінки/чоловіки);
  алкоголь дозволено, жорстких фільтрів нема.
- special — сегменти з обмеженнями (вагітні, діти, підлітки, спортсмени, детокс,
  за кермом) та стилем (клуб, гурмани).

Поля сегмента:
- id            стабільний слаг (іде у запит /recipes/generate)
- name          людська назва для UI
- group         adults | special
- alcohol_free  чи дозволені лише безалкогольні основи (0% ABV)
- suggest       чи підставляти авто-профіль (для «дорослі» — ні)
- forbidden_tags теги сировини, що жорстко виключаються (див. seed.MATERIAL_TAGS)
- default_profile базові ноти профілю (назви характеристик); до них додаються
                 1–2 природні ноти основної сировини
- disclaimer    застереження для банера (порожнє — без банера)

Профілі — усереднені «популярні» орієнтири за дослідженнями смакових уподобань;
користувач може їх змінити.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Теги-протипоказання (значення з seed.MATERIAL_TAGS)
TAG_PREGNANCY = "pregnancy_unsafe"
TAG_KIDS = "kids_unsafe"
TAG_CAFFEINE = "caffeine"

_PREG_NOTE = (
    "Лише безалкогольна основа. Виключено сировину, не рекомендовану під час "
    "вагітності та грудного вигодовування (полин, шавлія, мускатний горіх, "
    "лакриця, кофеїн тощо). Це не медична порада — проконсультуйтеся з лікарем."
)
_KIDS_NOTE = (
    "Лише безалкогольна основа. Виключено гостру, гірко-лікарську та кофеїнову "
    "сировину. Перед вживанням дитиною порадьтеся з педіатром."
)

AUDIENCES: List[Dict] = [
    # --- Дорослі (алкоголь дозволено) ---
    {
        "id": "adults",
        "name": "Дорослі",
        "group": "adults",
        "alcohol_free": False,
        "suggest": False,
        "forbidden_tags": [],
        "default_profile": [],
        "disclaimer": "",
    },
    {
        "id": "women",
        "name": "Жінки",
        "group": "adults",
        "alcohol_free": False,
        "suggest": True,
        "forbidden_tags": [],
        "default_profile": ["солодкий", "квітковий", "фруктовий"],
        "disclaimer": "",
    },
    {
        "id": "men",
        "name": "Чоловіки",
        "group": "adults",
        "alcohol_free": False,
        "suggest": True,
        "forbidden_tags": [],
        "default_profile": ["деревинний", "пряний", "цитрусовий", "терпкий"],
        "disclaimer": "",
    },
    # --- Сегменти з обмеженнями / стилем ---
    {
        "id": "pregnant",
        "name": "Вагітні / годуючі",
        "group": "special",
        "alcohol_free": True,
        "suggest": True,
        "forbidden_tags": [TAG_PREGNANCY, TAG_KIDS, TAG_CAFFEINE],
        "default_profile": ["фруктовий", "ягідний", "свіжий"],
        "disclaimer": _PREG_NOTE,
    },
    {
        "id": "kids",
        "name": "Діти",
        "group": "special",
        "alcohol_free": True,
        "suggest": True,
        "forbidden_tags": [TAG_KIDS, TAG_PREGNANCY, TAG_CAFFEINE],
        "default_profile": ["солодкий", "фруктовий", "ягідний"],
        "disclaimer": _KIDS_NOTE,
    },
    {
        "id": "teens",
        "name": "Підлітки",
        "group": "special",
        "alcohol_free": True,
        "suggest": True,
        "forbidden_tags": [TAG_KIDS, TAG_CAFFEINE],
        "default_profile": ["солодкий", "цитрусовий", "тропічний"],
        "disclaimer": "Лише безалкогольна основа. Без кофеїну та гострої сировини.",
    },
    {
        "id": "athletes",
        "name": "Спортсмени",
        "group": "special",
        "alcohol_free": True,
        "suggest": True,
        "forbidden_tags": [],
        "default_profile": ["свіжий", "цитрусовий", "ягідний"],
        "disclaimer": "Лише безалкогольна основа — освіжаючий ізотонічний стиль.",
    },
    {
        "id": "detox",
        "name": "Детокс / ЗСЖ",
        "group": "special",
        "alcohol_free": True,
        "suggest": True,
        "forbidden_tags": [],
        "default_profile": ["свіжий", "трав'яний", "цитрусовий"],
        "disclaimer": "Лише безалкогольна основа — легкий трав'яно-цитрусовий стиль.",
    },
    {
        "id": "driver",
        "name": "За кермом",
        "group": "special",
        "alcohol_free": True,
        "suggest": True,
        "forbidden_tags": [],
        "default_profile": ["свіжий", "фруктовий", "цитрусовий"],
        "disclaimer": "Лише безалкогольна основа — 0% алкоголю.",
    },
    {
        "id": "club",
        "name": "Клуб / вечірка",
        "group": "special",
        "alcohol_free": False,
        "suggest": True,
        "forbidden_tags": [],
        "default_profile": ["солодкий", "тропічний", "цитрусовий"],
        "disclaimer": "",
    },
    {
        "id": "gourmet",
        "name": "Гурмани",
        "group": "special",
        "alcohol_free": False,
        "suggest": True,
        "forbidden_tags": [],
        "default_profile": ["пряний", "деревинний", "гіркий", "бальзамічний"],
        "disclaimer": "",
    },
]

AUDIENCE_BY_ID: Dict[str, Dict] = {a["id"]: a for a in AUDIENCES}
DEFAULT_AUDIENCE_ID = "adults"


def get_audience(audience_id: Optional[str]) -> Optional[Dict]:
    if not audience_id:
        return None
    return AUDIENCE_BY_ID.get(audience_id)
