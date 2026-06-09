"""Наповнення бази даними з лекції "Алкоботаніка" (О. Громов).

Структура SEED_DATA одночасно є форматом для імпорту: її можна винести у JSON
і завантажувати тим самим кодом (load_data).

Формат:
{
  "characteristics": ["свіжий", "цитрусовий", ...],
  "bases": ["спирт пшеничний", ...],
  "compounds": [
     {"name": "лімонен", "kind": "aroma|taste|both",
      "characteristics": {"свіжий": 1.0, "цитрусовий": 1.0}}
  ],
  "materials": [
     {"name": "калина", "has_pit_variants": true,
      "compounds": [
         {"compound": "лімонен", "part": "whole", "form": "fresh",
          "pit": "na", "intensity": 0.8}
      ]}
  ]
}
part: whole | flower | zest | fruit | berry | leaf | root | bark | seed |
      herb | needle | rhizome | resin   (частина сировини / препарат)
form: fresh | dry | extract | oil | juice   (спосіб приготування)
pit:  with | without | na

Одна сировина (напр. "апельсин") може мати кілька частин/препаратів
(квіти-олія, цедра свіжа/суха, сік, екстракт) — у кожного свій профіль.

Дані відображають профіль сировини, а не точні концентрації — інтенсивності
задані експертно для ранжування композицій.
"""

from __future__ import annotations

from typing import Dict

from sqlalchemy import select

from .database import SessionLocal
from .models import (
    AromaCompound,
    Base_,
    Characteristic,
    CompoundCharacteristic,
    MaterialCompound,
    RawMaterial,
)

# Порядок характеристик для UI (аромат -> смак)
CHARACTERISTICS = [
    "свіжий",
    "цитрусовий",
    "лимонний",
    "хвойний",
    "деревинний",
    "квітковий",
    "фіалковий",
    "трояндовий",
    "лавандовий",
    "медовий",
    "ванільний",
    "фруктовий",
    "ягідний",
    "анісовий",
    "гвоздичний",
    "пряний",
    "мускатний",
    "камфорний",
    "евкаліптовий",
    "ментоловий",
    "м'ятний",
    "охолоджуючий",
    "трав'яний",
    "бальзамічний",
    "горіховий",
    "мигдальний",
    "кавовий",
    "шоколадний",
    "димний",
    "солодкий",
    "кислий",
    "гіркий",
    "терпкий",
    "пекучий",
]

# Аромосполуки: kind = aroma | taste | both, characteristics = {назва: вага}
COMPOUNDS = [
    {"name": "лімонен", "kind": "aroma", "characteristics": {"свіжий": 1.0, "цитрусовий": 1.0, "лимонний": 0.8}},
    {"name": "цитраль", "kind": "aroma", "characteristics": {"цитрусовий": 1.0, "лимонний": 1.0, "трав'яний": 0.5, "евкаліптовий": 0.4}},
    {"name": "мірцен", "kind": "aroma", "characteristics": {"трав'яний": 0.8, "хвойний": 0.5, "пряний": 0.4}},
    {"name": "α-пінен", "kind": "aroma", "characteristics": {"хвойний": 1.0, "деревинний": 0.8, "свіжий": 0.5}},
    {"name": "β-пінен", "kind": "aroma", "characteristics": {"деревинний": 0.9, "хвойний": 0.7}},
    {"name": "камфен", "kind": "aroma", "characteristics": {"хвойний": 0.8, "свіжий": 0.5, "охолоджуючий": 0.4}},
    {"name": "камфора", "kind": "both", "characteristics": {"камфорний": 1.0, "ментоловий": 0.7, "охолоджуючий": 0.7, "свіжий": 0.4}},
    {"name": "цинеол (евкаліптол)", "kind": "aroma", "characteristics": {"евкаліптовий": 1.0, "ментоловий": 0.6, "охолоджуючий": 0.6, "трав'яний": 0.5}},
    {"name": "ліналоол", "kind": "both", "characteristics": {"квітковий": 1.0, "лавандовий": 0.7, "свіжий": 0.5, "цитрусовий": 0.4}},
    {"name": "гераніол", "kind": "aroma", "characteristics": {"трояндовий": 1.0, "квітковий": 0.9, "фруктовий": 0.5}},
    {"name": "α-терпінеол", "kind": "aroma", "characteristics": {"квітковий": 0.7, "деревинний": 0.5}},
    {"name": "евгенол", "kind": "both", "characteristics": {"гвоздичний": 1.0, "пряний": 0.9, "деревинний": 0.6}},
    {"name": "каріофілен", "kind": "aroma", "characteristics": {"деревинний": 0.8, "пряний": 0.7}},
    {"name": "анетол", "kind": "both", "characteristics": {"анісовий": 1.0, "солодкий": 0.8}},
    {"name": "естрагол", "kind": "aroma", "characteristics": {"анісовий": 0.9, "деревинний": 0.4}},
    {"name": "кумарин", "kind": "both", "characteristics": {"солодкий": 0.7, "ванільний": 0.6, "трав'яний": 0.6}},
    {"name": "ванілін", "kind": "both", "characteristics": {"ванільний": 1.0, "солодкий": 0.8, "деревинний": 0.4}},
    {"name": "цинамальдегід", "kind": "both", "characteristics": {"пряний": 1.0, "солодкий": 0.6, "деревинний": 0.5}},
    {"name": "метилциннамат", "kind": "aroma", "characteristics": {"бальзамічний": 0.8, "фруктовий": 0.6, "пряний": 0.5}},
    {"name": "ірон", "kind": "aroma", "characteristics": {"фіалковий": 1.0, "квітковий": 0.6}},
    {"name": "азарон", "kind": "aroma", "characteristics": {"пряний": 0.9, "деревинний": 0.4}},
    {"name": "борнеол", "kind": "aroma", "characteristics": {"деревинний": 0.7, "камфорний": 0.6}},
    {"name": "тимол", "kind": "both", "characteristics": {"пряний": 0.9, "трав'яний": 0.6, "гіркий": 0.5}},
    {"name": "карвакрол", "kind": "both", "characteristics": {"пряний": 0.9, "трав'яний": 0.6}},
    {"name": "ментол", "kind": "both", "characteristics": {"ментоловий": 1.0, "м'ятний": 1.0, "охолоджуючий": 0.9, "свіжий": 0.5}},
    {"name": "карвон", "kind": "aroma", "characteristics": {"м'ятний": 0.7, "пряний": 0.6, "трав'яний": 0.5}},
    {"name": "апіол", "kind": "aroma", "characteristics": {"пряний": 0.8, "терпкий": 0.5}},
    {"name": "міристицин", "kind": "both", "characteristics": {"мускатний": 1.0, "пряний": 0.8, "деревинний": 0.5}},
    {"name": "селінен", "kind": "aroma", "characteristics": {"деревинний": 0.7, "пряний": 0.5}},
    {"name": "джинджерол", "kind": "taste", "characteristics": {"пекучий": 1.0, "пряний": 0.7}},
    {"name": "шогаол", "kind": "taste", "characteristics": {"пекучий": 0.9, "гіркий": 0.6}},
    {"name": "цингіберен", "kind": "aroma", "characteristics": {"деревинний": 0.8, "пряний": 0.4}},
    {"name": "піперин", "kind": "taste", "characteristics": {"пекучий": 1.0, "пряний": 0.6}},
    {"name": "капсаїцин", "kind": "taste", "characteristics": {"пекучий": 1.0}},
    {"name": "кубебін", "kind": "aroma", "characteristics": {"хвойний": 0.8, "деревинний": 0.7, "пряний": 0.6}},
    {"name": "сабінен", "kind": "aroma", "characteristics": {"деревинний": 0.6, "фруктовий": 0.5, "пряний": 0.4}},
    {"name": "піперитон", "kind": "aroma", "characteristics": {"м'ятний": 0.7, "свіжий": 0.6}},
    {"name": "β-фелландрен", "kind": "aroma", "characteristics": {"хвойний": 0.7, "цитрусовий": 0.5}},
    {"name": "туйон", "kind": "both", "characteristics": {"гіркий": 0.7, "камфорний": 0.6, "трав'яний": 0.5}},
    {"name": "фарнезол", "kind": "aroma", "characteristics": {"медовий": 0.9, "квітковий": 0.7, "солодкий": 0.5}},
    {"name": "сафраналь", "kind": "aroma", "characteristics": {"пряний": 0.9, "медовий": 0.4}},
    {"name": "пікрокроцин", "kind": "taste", "characteristics": {"гіркий": 0.8, "пряний": 0.5}},
    {"name": "гентіопікрин", "kind": "taste", "characteristics": {"гіркий": 1.0}},
    {"name": "амарогентин", "kind": "taste", "characteristics": {"гіркий": 1.0}},
    {"name": "хінін", "kind": "taste", "characteristics": {"гіркий": 1.0}},
    {"name": "амигдалін", "kind": "taste", "characteristics": {"гіркий": 0.9, "мигдальний": 0.7}},
    {"name": "бензальдегід", "kind": "both", "characteristics": {"мигдальний": 1.0, "солодкий": 0.5}},
    {"name": "танін", "kind": "taste", "characteristics": {"терпкий": 1.0, "гіркий": 0.5}},
    {"name": "катехіни", "kind": "taste", "characteristics": {"терпкий": 0.8}},
    {"name": "флавоноїди", "kind": "taste", "characteristics": {"терпкий": 0.6, "гіркий": 0.5}},
    {"name": "антоціани", "kind": "taste", "characteristics": {"ягідний": 1.0, "терпкий": 0.4}},
    {"name": "юглон", "kind": "both", "characteristics": {"горіховий": 0.9, "терпкий": 0.6}},
    {"name": "гексенал", "kind": "aroma", "characteristics": {"трав'яний": 0.7, "свіжий": 0.6}},
    {"name": "кофеїн", "kind": "taste", "characteristics": {"гіркий": 0.9}},
    {"name": "теобромін", "kind": "taste", "characteristics": {"гіркий": 0.7}},
    {"name": "кофеоль", "kind": "aroma", "characteristics": {"кавовий": 1.0, "димний": 0.5, "шоколадний": 0.5}},
    {"name": "гліциризин", "kind": "taste", "characteristics": {"солодкий": 1.0}},
    {"name": "гумулен", "kind": "aroma", "characteristics": {"деревинний": 0.7, "трав'яний": 0.4}},
    {"name": "органічні кислоти", "kind": "taste", "characteristics": {"кислий": 1.0}},
]


def _m(compound, form="dry", pit="na", intensity=1.0, part="whole"):
    return {
        "compound": compound,
        "part": part,
        "form": form,
        "pit": pit,
        "intensity": intensity,
    }


MATERIALS = [
    # --- Коріння та кореневища ---
    {"name": "аїр болотний", "has_pit_variants": False, "compounds": [
        _m("азарон", "dry", "na", 1.0), _m("евгенол", "dry", "na", 0.6),
        _m("камфора", "dry", "na", 0.5), _m("ліналоол", "dry", "na", 0.4),
        _m("α-пінен", "dry", "na", 0.4), _m("азарон", "extract", "na", 1.3),
    ]},
    {"name": "гравілат міський", "has_pit_variants": False, "compounds": [
        _m("евгенол", "dry", "na", 1.0), _m("гераніол", "dry", "na", 0.5),
        _m("танін", "dry", "na", 0.6),
    ]},
    {"name": "ірис (фіалковий корінь)", "has_pit_variants": False, "compounds": [
        _m("ірон", "dry", "na", 1.0), _m("ліналоол", "dry", "na", 0.5),
        _m("гераніол", "dry", "na", 0.4), _m("ірон", "extract", "na", 1.3),
    ]},
    {"name": "калган (альпінія)", "has_pit_variants": False, "compounds": [
        _m("цинеол (евкаліптол)", "dry", "na", 1.0), _m("камфора", "dry", "na", 0.6),
        _m("метилциннамат", "dry", "na", 0.5),
        # свіжий корінь — соковитіший, гостріший
        _m("цинеол (евкаліптол)", "fresh", "na", 0.9), _m("камфора", "fresh", "na", 0.5),
    ]},
    {"name": "валеріана", "has_pit_variants": False, "compounds": [
        _m("борнеол", "dry", "na", 0.8), _m("камфен", "dry", "na", 0.7),
        _m("α-пінен", "dry", "na", 0.6), _m("лімонен", "dry", "na", 0.4),
        _m("борнеол", "extract", "na", 1.0), _m("камфен", "extract", "na", 0.8),
    ]},
    {"name": "імбир", "has_pit_variants": False, "compounds": [
        _m("джинджерол", "fresh", "na", 1.0), _m("цингіберен", "fresh", "na", 0.8),
        _m("цитраль", "fresh", "na", 0.4), _m("цинеол (евкаліптол)", "fresh", "na", 0.4),
        _m("джинджерол", "dry", "na", 1.1), _m("шогаол", "dry", "na", 0.7),
        _m("цингіберен", "dry", "na", 0.6),
    ]},
    {"name": "горечавка жовта (тирлич)", "has_pit_variants": False, "compounds": [
        _m("гентіопікрин", "dry", "na", 1.0), _m("амарогентин", "dry", "na", 1.0),
    ]},
    {"name": "горець зміїний", "has_pit_variants": False, "compounds": [
        _m("танін", "dry", "na", 1.0), _m("катехіни", "dry", "na", 0.8),
        _m("флавоноїди", "dry", "na", 0.5),
    ]},
    {"name": "солодка (лакриця)", "has_pit_variants": False, "compounds": [
        _m("гліциризин", "dry", "na", 1.0), _m("анетол", "dry", "na", 0.7),
        _m("естрагол", "dry", "na", 0.5), _m("цинеол (евкаліптол)", "dry", "na", 0.3),
        # екстракт — концентрована солодкість
        _m("гліциризин", "extract", "na", 1.4), _m("анетол", "extract", "na", 0.8),
    ]},
    {"name": "любисток", "has_pit_variants": False, "compounds": [
        _m("апіол", "dry", "na", 0.7), _m("лімонен", "dry", "na", 0.5),
        _m("β-пінен", "dry", "na", 0.6), _m("кумарин", "dry", "na", 0.5),
        _m("міристицин", "dry", "na", 0.4), _m("селінен", "dry", "na", 0.5),
    ]},
    {"name": "девясил", "has_pit_variants": False, "compounds": [
        _m("камфора", "dry", "na", 0.7), _m("цингіберен", "dry", "na", 0.4),
    ]},
    {"name": "селера (корінь)", "has_pit_variants": False, "compounds": [
        _m("лімонен", "fresh", "na", 0.8), _m("гумулен", "fresh", "na", 0.6),
        _m("лімонен", "dry", "na", 0.7),
    ]},
    {"name": "петрушка", "has_pit_variants": False, "compounds": [
        # зелень свіжа
        _m("апіол", "fresh", "na", 0.7, part="herb"),
        _m("камфора", "fresh", "na", 0.4, part="herb"),
        _m("гексенал", "fresh", "na", 0.4, part="herb"),
        # зелень суха
        _m("апіол", "dry", "na", 0.5, part="herb"),
        # насіння — концентрований апіол
        _m("апіол", "dry", "na", 1.0, part="seed"),
    ]},

    # --- Трави та листя ---
    {"name": "душиця (орегано)", "has_pit_variants": False, "compounds": [
        _m("тимол", "dry", "na", 0.9), _m("карвакрол", "dry", "na", 0.9),
        _m("тимол", "fresh", "na", 0.7), _m("карвакрол", "fresh", "na", 0.7),
    ]},
    {"name": "чебрець (тим'ян)", "has_pit_variants": False, "compounds": [
        _m("тимол", "dry", "na", 1.0), _m("лімонен", "dry", "na", 0.4),
        _m("цитраль", "dry", "na", 0.4), _m("тимол", "fresh", "na", 0.8),
    ]},
    {"name": "чабер", "has_pit_variants": False, "compounds": [
        _m("карвакрол", "dry", "na", 1.0), _m("тимол", "dry", "na", 0.5),
        _m("карвакрол", "fresh", "na", 0.8), _m("тимол", "fresh", "na", 0.4),
    ]},
    {"name": "іссоп", "has_pit_variants": False, "compounds": [
        _m("камфора", "dry", "na", 0.7), _m("цинеол (евкаліптол)", "dry", "na", 0.6),
        _m("ліналоол", "dry", "na", 0.4),
        _m("камфора", "fresh", "na", 0.6), _m("цинеол (евкаліптол)", "fresh", "na", 0.5),
    ]},
    {"name": "лаванда", "has_pit_variants": False, "compounds": [
        _m("ліналоол", "fresh", "na", 1.0), _m("камфора", "fresh", "na", 0.4),
        _m("цинеол (евкаліптол)", "fresh", "na", 0.4), _m("ліналоол", "dry", "na", 0.9),
    ]},
    {"name": "меліса", "has_pit_variants": False, "compounds": [
        _m("цитраль", "fresh", "na", 0.9), _m("гераніол", "fresh", "na", 0.5),
        _m("ліналоол", "fresh", "na", 0.4), _m("цитраль", "dry", "na", 0.6),
    ]},
    {"name": "шавлія", "has_pit_variants": False, "compounds": [
        _m("камфора", "dry", "na", 0.7), _m("туйон", "dry", "na", 0.6),
        _m("ліналоол", "dry", "na", 0.4),
        _m("камфора", "fresh", "na", 0.6), _m("туйон", "fresh", "na", 0.5),
    ]},
    {"name": "зубровка", "has_pit_variants": False, "compounds": [
        _m("кумарин", "dry", "na", 1.0),
    ]},
    {"name": "донник", "has_pit_variants": False, "compounds": [
        _m("кумарин", "dry", "na", 1.0),
    ]},
    {"name": "полин", "has_pit_variants": False, "compounds": [
        _m("туйон", "dry", "na", 1.0), _m("камфора", "dry", "na", 0.4),
        _m("туйон", "fresh", "na", 0.8), _m("камфора", "fresh", "na", 0.3),
    ]},
    {"name": "м'ята перечна", "has_pit_variants": False, "compounds": [
        _m("ментол", "fresh", "na", 1.0), _m("лімонен", "fresh", "na", 0.3),
        _m("ментол", "dry", "na", 1.1), _m("карвон", "dry", "na", 0.4),
    ]},
    {"name": "лемонграс", "has_pit_variants": False, "compounds": [
        _m("цитраль", "fresh", "na", 1.2), _m("гераніол", "fresh", "na", 0.6),
        _m("цитраль", "dry", "na", 1.0),
    ]},
    {"name": "лавровий лист", "has_pit_variants": False, "compounds": [
        _m("цинеол (евкаліптол)", "dry", "na", 1.0), _m("евгенол", "dry", "na", 0.5),
        _m("β-фелландрен", "dry", "na", 0.5),
        # свіжий лист — яскравіший, трохи гіркіший
        _m("цинеол (евкаліптол)", "fresh", "na", 1.1), _m("евгенол", "fresh", "na", 0.4),
    ]},
    {"name": "мирт", "has_pit_variants": False, "compounds": [
        _m("камфора", "dry", "na", 0.7), _m("α-пінен", "dry", "na", 0.6),
        _m("флавоноїди", "dry", "na", 0.4),
        _m("камфора", "fresh", "na", 0.6), _m("α-пінен", "fresh", "na", 0.5),
    ]},
    {"name": "лимонний мирт", "has_pit_variants": False, "compounds": [
        _m("цитраль", "dry", "na", 1.3), _m("мірцен", "dry", "na", 0.5),
        _m("ліналоол", "dry", "na", 0.4),
        _m("цитраль", "fresh", "na", 1.1), _m("мірцен", "fresh", "na", 0.4),
    ]},
    {"name": "листя горіха", "has_pit_variants": False, "compounds": [
        _m("юглон", "dry", "na", 1.0), _m("юглон", "fresh", "na", 0.8),
    ]},

    # --- Квіти ---
    {"name": "троянда чайна", "has_pit_variants": False, "compounds": [
        # пелюстки свіжі
        _m("гераніол", "fresh", "na", 1.0), _m("ліналоол", "fresh", "na", 0.7),
        _m("фарнезол", "fresh", "na", 0.5),
        # пелюстки сухі
        _m("гераніол", "dry", "na", 0.8), _m("фарнезол", "dry", "na", 0.4),
        # трояндова олія — концентрат
        _m("гераніол", "oil", "na", 1.4), _m("ліналоол", "oil", "na", 0.8),
        _m("фарнезол", "oil", "na", 0.7),
    ]},
    {"name": "бузина чорна", "has_pit_variants": False, "compounds": [
        # квіти — квітково-медовий аромат, майже без смаку
        _m("ліналоол", "fresh", "na", 0.8, part="flower"),
        _m("фарнезол", "fresh", "na", 0.6, part="flower"),
        _m("ліналоол", "dry", "na", 0.6, part="flower"),
        _m("фарнезол", "dry", "na", 0.4, part="flower"),
        # ягоди — ягідно-терпкий смак, інший профіль
        _m("антоціани", "fresh", "na", 1.0, part="berry"),
        _m("органічні кислоти", "fresh", "na", 0.4, part="berry"),
        _m("антоціани", "dry", "na", 0.8, part="berry"),
        _m("антоціани", "extract", "na", 1.2, part="berry"),
        _m("органічні кислоти", "extract", "na", 0.3, part="berry"),
    ]},
    {"name": "липа", "has_pit_variants": False, "compounds": [
        _m("фарнезол", "dry", "na", 0.9), _m("ліналоол", "dry", "na", 0.5),
        _m("фарнезол", "fresh", "na", 0.8), _m("ліналоол", "fresh", "na", 0.5),
    ]},
    {"name": "акація біла", "has_pit_variants": False, "compounds": [
        _m("ліналоол", "fresh", "na", 0.9), _m("α-терпінеол", "fresh", "na", 0.6),
        _m("ліналоол", "dry", "na", 0.7), _m("α-терпінеол", "dry", "na", 0.4),
    ]},
    {"name": "шафран", "has_pit_variants": False, "compounds": [
        _m("сафраналь", "dry", "na", 1.0), _m("пікрокроцин", "dry", "na", 0.7),
    ]},

    # --- Кора ---
    {"name": "кориця цейлонська", "has_pit_variants": False, "compounds": [
        _m("цинамальдегід", "dry", "na", 1.2), _m("евгенол", "dry", "na", 0.5),
        _m("ліналоол", "dry", "na", 0.4), _m("каріофілен", "dry", "na", 0.4),
    ]},
    {"name": "кассія (китайська кориця)", "has_pit_variants": False, "compounds": [
        _m("цинамальдегід", "dry", "na", 1.3), _m("кумарин", "dry", "na", 0.6),
        _m("цинеол (евкаліптол)", "dry", "na", 0.3),
    ]},
    {"name": "дубова кора", "has_pit_variants": False, "compounds": [
        _m("танін", "dry", "na", 1.0), _m("флавоноїди", "dry", "na", 0.5),
    ]},
    {"name": "хінна кора", "has_pit_variants": False, "compounds": [
        _m("хінін", "dry", "na", 1.0),
    ]},

    # --- Плоди, насіння, спеції ---
    {"name": "мускатний горіх", "has_pit_variants": False, "compounds": [
        _m("міристицин", "dry", "na", 1.2),
    ]},
    {"name": "гвоздика", "has_pit_variants": False, "compounds": [
        _m("евгенол", "dry", "na", 1.3), _m("каріофілен", "dry", "na", 0.6),
    ]},
    {"name": "аніс", "has_pit_variants": False, "compounds": [
        _m("анетол", "dry", "na", 1.2),
    ]},
    {"name": "фенхель", "has_pit_variants": False, "compounds": [
        # насіння — солодко-анісовий
        _m("анетол", "dry", "na", 1.0, part="seed"),
        _m("естрагол", "dry", "na", 0.5, part="seed"),
        # зелень свіжа — легший анісово-трав'яний
        _m("анетол", "fresh", "na", 0.6, part="herb"),
        _m("гексенал", "fresh", "na", 0.4, part="herb"),
    ]},
    {"name": "бадьян", "has_pit_variants": False, "compounds": [
        _m("анетол", "dry", "na", 1.3),
    ]},
    {"name": "ваніль", "has_pit_variants": False, "compounds": [
        _m("ванілін", "dry", "na", 1.2), _m("ванілін", "extract", "na", 1.4),
    ]},
    {"name": "кардамон", "has_pit_variants": False, "compounds": [
        _m("цинеол (евкаліптол)", "dry", "na", 0.9), _m("ліналоол", "dry", "na", 0.5),
    ]},
    {"name": "коріандр", "has_pit_variants": False, "compounds": [
        # насіння — теплий пряно-цитрусовий тон
        _m("ліналоол", "dry", "na", 1.0, part="seed"),
        _m("ліналоол", "extract", "na", 1.2, part="seed"),
        # зелень (кінза) свіжа — трав'яно-свіжий аромат
        _m("гексенал", "fresh", "na", 0.9, part="herb"),
        _m("ліналоол", "fresh", "na", 0.4, part="herb"),
    ]},
    {"name": "тмин", "has_pit_variants": False, "compounds": [
        _m("карвон", "dry", "na", 1.0, part="seed"),
        _m("лімонен", "dry", "na", 0.5, part="seed"),
    ]},
    {"name": "кріп", "has_pit_variants": False, "compounds": [
        # зелень свіжа — м'який трав'яно-пряний аромат
        _m("гексенал", "fresh", "na", 0.7, part="herb"),
        _m("карвон", "fresh", "na", 0.6, part="herb"),
        _m("лімонен", "fresh", "na", 0.3, part="herb"),
        # зелень суха
        _m("карвон", "dry", "na", 0.7, part="herb"),
        _m("лімонен", "dry", "na", 0.4, part="herb"),
        # насіння — концентрований карвон
        _m("карвон", "dry", "na", 1.1, part="seed"),
        _m("лімонен", "dry", "na", 0.6, part="seed"),
    ]},
    {"name": "ялівець", "has_pit_variants": False, "compounds": [
        _m("α-пінен", "dry", "na", 1.0), _m("мірцен", "dry", "na", 0.6),
        _m("лімонен", "dry", "na", 0.4), _m("α-пінен", "fresh", "na", 0.9),
        _m("α-пінен", "extract", "na", 1.3),
    ]},
    {"name": "чорний перець", "has_pit_variants": False, "compounds": [
        _m("піперин", "dry", "na", 1.0), _m("каріофілен", "dry", "na", 0.6),
        _m("мірцен", "dry", "na", 0.5), _m("α-пінен", "dry", "na", 0.4),
    ]},
    {"name": "кубеба", "has_pit_variants": False, "compounds": [
        _m("кубебін", "dry", "na", 1.2), _m("сабінен", "dry", "na", 0.5),
        _m("мірцен", "dry", "na", 0.5),
    ]},
    {"name": "рожевий перець", "has_pit_variants": False, "compounds": [
        _m("лімонен", "dry", "na", 0.8), _m("піперитон", "dry", "na", 0.6),
        _m("β-фелландрен", "dry", "na", 0.5),
    ]},
    {"name": "червоний гострий перець", "has_pit_variants": False, "compounds": [
        _m("капсаїцин", "dry", "na", 1.0), _m("капсаїцин", "fresh", "na", 0.6),
    ]},

    # --- Цитрусові (цедра / сік / олія мають різні профілі) ---
    {"name": "лимон", "has_pit_variants": False, "compounds": [
        # цедра свіжа — яскравий лимонний аромат
        _m("лімонен", "fresh", "na", 1.3, part="zest"),
        _m("цитраль", "fresh", "na", 0.8, part="zest"),
        _m("гераніол", "fresh", "na", 0.4, part="zest"),
        # цедра суха
        _m("лімонен", "dry", "na", 1.0, part="zest"),
        _m("цитраль", "dry", "na", 0.5, part="zest"),
        # лимонна ефірна олія — концентрат
        _m("лімонен", "oil", "na", 1.6, part="zest"),
        _m("цитраль", "oil", "na", 0.9, part="zest"),
        # сік — виразно кислий, легкий цитрус
        _m("органічні кислоти", "juice", "na", 1.0, part="fruit"),
        _m("лімонен", "juice", "na", 0.3, part="fruit"),
        # екстракт плоду
        _m("лімонен", "extract", "na", 1.0, part="fruit"),
        _m("органічні кислоти", "extract", "na", 0.6, part="fruit"),
        _m("цитраль", "extract", "na", 0.4, part="fruit"),
    ]},
    {"name": "апельсин", "has_pit_variants": False, "compounds": [
        # квіти (нероліва олія) — квітковий аромат
        _m("ліналоол", "oil", "na", 1.0, part="flower"),
        _m("гераніол", "oil", "na", 0.6, part="flower"),
        _m("фарнезол", "oil", "na", 0.4, part="flower"),
        # цедра свіжа — яскравий цитрус
        _m("лімонен", "fresh", "na", 1.3, part="zest"),
        _m("ліналоол", "fresh", "na", 0.5, part="zest"),
        _m("цитраль", "fresh", "na", 0.4, part="zest"),
        # цедра суха — приглушеніший цитрус
        _m("лімонен", "dry", "na", 1.0, part="zest"),
        _m("ліналоол", "dry", "na", 0.3, part="zest"),
        # апельсинова ефірна олія — концентрований цитрус
        _m("лімонен", "oil", "na", 1.6, part="zest"),
        _m("ліналоол", "oil", "na", 0.5, part="zest"),
        # сік — кисло-фруктовий смак, слабкий аромат
        _m("органічні кислоти", "juice", "na", 0.8, part="fruit"),
        _m("гераніол", "juice", "na", 0.4, part="fruit"),
        _m("лімонен", "juice", "na", 0.3, part="fruit"),
        # екстракт цілого плоду
        _m("лімонен", "extract", "na", 1.0, part="fruit"),
        _m("органічні кислоти", "extract", "na", 0.5, part="fruit"),
        _m("ліналоол", "extract", "na", 0.4, part="fruit"),
    ]},
    {"name": "лайм", "has_pit_variants": False, "compounds": [
        # цедра свіжа
        _m("лімонен", "fresh", "na", 1.2, part="zest"),
        _m("цитраль", "fresh", "na", 0.7, part="zest"),
        # цедра суха
        _m("лімонен", "dry", "na", 0.9, part="zest"),
        # цедрова олія
        _m("лімонен", "oil", "na", 1.5, part="zest"),
        _m("цитраль", "oil", "na", 0.8, part="zest"),
        # сік — кислий
        _m("органічні кислоти", "juice", "na", 1.0, part="fruit"),
        _m("лімонен", "juice", "na", 0.3, part="fruit"),
    ]},
    {"name": "грейпфрут", "has_pit_variants": False, "compounds": [
        # цедра свіжа — цитрус + гірчинка
        _m("лімонен", "fresh", "na", 1.1, part="zest"),
        _m("флавоноїди", "fresh", "na", 0.6, part="zest"),
        # цедра суха
        _m("лімонен", "dry", "na", 0.9, part="zest"),
        _m("флавоноїди", "dry", "na", 0.5, part="zest"),
        # сік — кисло-гіркуватий
        _m("органічні кислоти", "juice", "na", 0.8, part="fruit"),
        _m("флавоноїди", "juice", "na", 0.5, part="fruit"),
        _m("лімонен", "juice", "na", 0.3, part="fruit"),
    ]},
    {"name": "мандарин", "has_pit_variants": False, "compounds": [
        # цедра свіжа — м'який солодкий цитрус
        _m("лімонен", "fresh", "na", 1.0, part="zest"),
        _m("ліналоол", "fresh", "na", 0.4, part="zest"),
        # цедра суха
        _m("лімонен", "dry", "na", 0.8, part="zest"),
        # сік — м'який кисло-солодкий
        _m("органічні кислоти", "juice", "na", 0.6, part="fruit"),
        _m("гераніол", "juice", "na", 0.3, part="fruit"),
        _m("лімонен", "juice", "na", 0.3, part="fruit"),
    ]},

    # --- Біостимулятори / інше ---
    {"name": "кава", "has_pit_variants": False, "compounds": [
        _m("кофеїн", "dry", "na", 0.9), _m("кофеоль", "dry", "na", 1.0),
    ]},
    {"name": "какао боби", "has_pit_variants": False, "compounds": [
        _m("теобромін", "dry", "na", 0.8), _m("кофеоль", "dry", "na", 0.6),
    ]},

    # --- Ягоди/плоди з кісточкою (демонстрація вибору кісточки) ---
    {"name": "калина", "has_pit_variants": True, "compounds": [
        _m("антоціани", "fresh", "without", 1.0), _m("лімонен", "fresh", "without", 0.3),
        _m("антоціани", "fresh", "with", 1.0), _m("амигдалін", "fresh", "with", 0.6),
        _m("бензальдегід", "fresh", "with", 0.5),
        _m("антоціани", "dry", "without", 0.8), _m("антоціани", "extract", "na", 1.2),
    ]},
    {"name": "вишня", "has_pit_variants": True, "compounds": [
        # свіжа без кісточки — ягідно-кисла
        _m("антоціани", "fresh", "without", 0.9), _m("бензальдегід", "fresh", "without", 0.2),
        _m("органічні кислоти", "fresh", "without", 0.4),
        # свіжа з кісточкою — мигдально-вишневий тон
        _m("бензальдегід", "fresh", "with", 0.9), _m("амигдалін", "fresh", "with", 0.6),
        _m("антоціани", "fresh", "with", 0.7),
        # сушена вишня — концентрована ягода
        _m("антоціани", "dry", "without", 0.6), _m("бензальдегід", "dry", "without", 0.3),
        # екстракт / настоянка
        _m("антоціани", "extract", "na", 1.0), _m("бензальдегід", "extract", "na", 0.4),
    ]},
    {"name": "абрикос", "has_pit_variants": True, "compounds": [
        # свіжий без кісточки — кисло-фруктовий
        _m("органічні кислоти", "fresh", "without", 0.6), _m("лімонен", "fresh", "without", 0.2),
        _m("гераніол", "fresh", "without", 0.3),
        # свіжий з кісточкою — мигдальний тон ядра
        _m("амигдалін", "fresh", "with", 0.7), _m("бензальдегід", "fresh", "with", 0.8),
        # курага (сушений, без кісточки) — солодко-фруктова, м'якша кислота
        _m("гераніол", "dry", "without", 0.4), _m("органічні кислоти", "dry", "without", 0.4),
        _m("бензальдегід", "dry", "without", 0.2),
        # курага з кісточкою — більше мигдалю
        _m("бензальдегід", "dry", "with", 0.6), _m("амигдалін", "dry", "with", 0.5),
        # екстракт плоду
        _m("гераніол", "extract", "na", 0.5), _m("органічні кислоти", "extract", "na", 0.5),
        _m("бензальдегід", "extract", "na", 0.3),
    ]},
]

SEED_DATA: Dict = {
    "characteristics": CHARACTERISTICS,
    "bases": [
        "спирт пшеничний",
        "спирт цукровий",
        "вино червоне",
        "вино біле",
    ],
    "compounds": COMPOUNDS,
    "materials": MATERIALS,
}


def load_data(data: Dict) -> None:
    """Завантажити структуру даних у базу (ідемпотентно за іменами)."""
    db = SessionLocal()
    try:
        char_by_name: Dict[str, Characteristic] = {}
        for name in data.get("characteristics", []):
            obj = db.scalar(select(Characteristic).where(Characteristic.name == name))
            if obj is None:
                obj = Characteristic(name=name)
                db.add(obj)
                db.flush()
            char_by_name[name] = obj

        for name in data.get("bases", []):
            if db.scalar(select(Base_).where(Base_.name == name)) is None:
                db.add(Base_(name=name))

        comp_by_name: Dict[str, AromaCompound] = {}
        for c in data.get("compounds", []):
            obj = db.scalar(select(AromaCompound).where(AromaCompound.name == c["name"]))
            if obj is None:
                obj = AromaCompound(name=c["name"], kind=c.get("kind", "both"))
                db.add(obj)
                db.flush()
            comp_by_name[c["name"]] = obj
            for char_name, weight in c.get("characteristics", {}).items():
                char = char_by_name.get(char_name)
                if char is None:
                    char = Characteristic(name=char_name)
                    db.add(char)
                    db.flush()
                    char_by_name[char_name] = char
                exists = db.scalar(
                    select(CompoundCharacteristic).where(
                        CompoundCharacteristic.compound_id == obj.id,
                        CompoundCharacteristic.characteristic_id == char.id,
                    )
                )
                if exists is None:
                    db.add(
                        CompoundCharacteristic(
                            compound_id=obj.id,
                            characteristic_id=char.id,
                            weight=float(weight),
                        )
                    )

        for m in data.get("materials", []):
            mat = db.scalar(select(RawMaterial).where(RawMaterial.name == m["name"]))
            if mat is None:
                mat = RawMaterial(
                    name=m["name"],
                    has_pit_variants=bool(m.get("has_pit_variants", False)),
                )
                db.add(mat)
                db.flush()
            for link in m.get("compounds", []):
                comp = comp_by_name.get(link["compound"])
                if comp is None:
                    comp = AromaCompound(name=link["compound"], kind="both")
                    db.add(comp)
                    db.flush()
                    comp_by_name[link["compound"]] = comp
                exists = db.scalar(
                    select(MaterialCompound).where(
                        MaterialCompound.raw_material_id == mat.id,
                        MaterialCompound.compound_id == comp.id,
                        MaterialCompound.part == link.get("part", "whole"),
                        MaterialCompound.form == link.get("form", "fresh"),
                        MaterialCompound.pit == link.get("pit", "na"),
                    )
                )
                if exists is None:
                    db.add(
                        MaterialCompound(
                            raw_material_id=mat.id,
                            compound_id=comp.id,
                            part=link.get("part", "whole"),
                            form=link.get("form", "fresh"),
                            pit=link.get("pit", "na"),
                            intensity=float(link.get("intensity", 1.0)),
                        )
                    )
        db.commit()
    finally:
        db.close()


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        has_data = db.scalar(select(RawMaterial.id).limit(1)) is not None
    finally:
        db.close()
    if not has_data:
        load_data(SEED_DATA)
