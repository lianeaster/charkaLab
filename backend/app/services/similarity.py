"""Перевірка згенерованої композиції на схожість з відомими рецептурами.

Склад композиції звіряється з довідником відомих напоїв (`known_drinks.py`) —
локально, без зовнішніх сервісів. Веб-пошук тут не допоміг би: пошуковик не
знає, що «ялівець + коріандр + дягель + ірис + цитрус» — це джин, і за таким
запитом віддає випадкові блоги про настоянки.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..known_drinks import ANY, KNOWN_DRINKS, KnownDrink, base_kind
from ..schemas import RecipeSimilarity, RecipeVariant

# Поріг, з якого повідомляємо про схожість.
SIMILARITY_THRESHOLD = 0.60

# Ваги підсумкової оцінки:
#  coverage — яка частка ВАШОГО складу пояснюється цією рецептурою (чи не
#             намішано зайвого, чого в тому напої немає);
#  depth    — наскільки повно відтворено характерний набір самого напою
#             (щоб сама лише ялівцівка не видавалась повноцінним джином).
W_COVERAGE = 0.6
W_DEPTH = 0.4
# Глибину рахуємо не від усього переліку рецептури (він буває довгим), а від
# кількох її ключових складників — інакше жоден реальний рецепт не дотягне.
DEPTH_REFERENCE = 5
# Скільки схожих рецептур показувати (композиція може нагадувати не один напій).
MAX_MATCHES = 2

_PARENS_RE = re.compile(r"\([^)]*\)")

# Ролі, що не є ароматичною сировиною композиції.
_SKIP_ROLES = {"base_spirit"}


def _normalize(name: str) -> str:
    return " ".join(name.lower().replace("’", "'").split())


def _same_ingredient(a: str, b: str) -> bool:
    """Чи це та сама сировина.

    Обидві назви походять з одного словника (`known_drinks.py` написаний
    точними назвами з бази сировини), тож звіряємо строго. Нечіткий збіг за
    коренем тут шкодить: «м'ята перечна» починала б збігатися з «духмяний
    перець». Єдина поблажка — уточнення в дужках, щоб «ірис» дорівнював
    «ірис (фіалковий корінь)».
    """
    na, nb = _normalize(a), _normalize(b)
    if na == nb:
        return True
    sa = _normalize(_PARENS_RE.sub("", na))
    sb = _normalize(_PARENS_RE.sub("", nb))
    return bool(sa) and bool(sb) and sa == sb


def _recipe_ingredients(variant: RecipeVariant) -> List[str]:
    """Ароматична сировина композиції (підсолоджувач лишаємо: мед — реальний
    маркер рецептур на кшталт крупника чи хтабентуну)."""
    return [m.name for m in variant.materials if m.role not in _SKIP_ROLES]


def _score_drink(
    drink: KnownDrink, ingredients: List[str], base: Optional[str]
) -> Tuple[float, List[str]]:
    """Оцінка схожості композиції з однією рецептурою.

    Повертає (оцінка 0..1, перелік збіглої сировини). Оцінка 0 означає, що
    це точно не той напій (немає визначальної сировини або несумісна основа).
    """
    kinds = set(drink.bases)
    if ANY not in kinds and base_kind(base) not in kinds:
        return 0.0, []  # напр. джин на червоному вині — це вже не джин

    # Визначальна сировина має бути присутня вся.
    for must in drink.core:
        if not any(_same_ingredient(must, ing) for ing in ingredients):
            return 0.0, []

    signature = list(drink.core) + list(drink.typical)
    matched: List[str] = []
    for ing in ingredients:
        for sig in signature:
            if _same_ingredient(sig, ing):
                matched.append(ing)
                break

    if len(matched) < drink.min_match:
        return 0.0, []

    coverage = len(matched) / len(ingredients) if ingredients else 0.0
    depth = min(1.0, len(matched) / min(len(signature), DEPTH_REFERENCE))
    return W_COVERAGE * coverage + W_DEPTH * depth, matched


def _rank_known_drinks(
    variant: RecipeVariant, base: Optional[str]
) -> List[Tuple[KnownDrink, float, List[str]]]:
    """Схожі рецептури, від найближчої. Композиція цілком може нагадувати
    кілька напоїв одразу — повертаємо всі, що перетнули поріг."""
    ingredients = _recipe_ingredients(variant)
    if not ingredients:
        return []
    scored: List[Tuple[KnownDrink, float, List[str]]] = []
    for drink in KNOWN_DRINKS:
        score, matched = _score_drink(drink, ingredients, base)
        if score > SIMILARITY_THRESHOLD:
            scored.append((drink, score, matched))
    scored.sort(key=lambda t: t[1], reverse=True)

    # Другим збігом показуємо напій ІНШОГО типу: «Steinhäger + Боровічка» —
    # це фактично одна відповідь двічі, а «джин + трав'яний лікер» уже дає
    # користувачу дві різні рамки, у які вписується його композиція.
    picked: List[Tuple[KnownDrink, float, List[str]]] = []
    seen_kinds: Set[str] = set()
    for item in scored:
        if item[0].kind in seen_kinds:
            continue
        picked.append(item)
        seen_kinds.add(item[0].kind)
        if len(picked) >= MAX_MATCHES:
            break
    return picked


def check(variant: RecipeVariant, base_name: Optional[str] = None) -> None:
    """Заповнює variant.similarities схожими відомими рецептурами."""
    matches = []
    for drink, score, matched in _rank_known_drinks(variant, base_name):
        gi_mark = ", із захищеним географічним зазначенням" if drink.gi else ""
        note = (
            f"{drink.kind}, {drink.origin}{gi_mark}. "
            f"Спільна сировина: {', '.join(matched)}."
        )
        if drink.note:
            note += f" {drink.note}"
        matches.append(
            RecipeSimilarity(
                percent=round(score * 100),
                drink=drink.name,
                matched=matched,
                note=note,
            )
        )
    variant.similarities = matches
