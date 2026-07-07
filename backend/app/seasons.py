"""Сезонність свіжої сировини.

Сезонність стосується ЛИШЕ свіжої форми (fresh): сушені, екстракт, олія та сік
доступні цілий рік. Тому позасезонну свіжу сировину алгоритм не пропонує, а якщо
її обрав сам користувач — попереджає й радить «зимову» форму (суху чи екстракт).

`MATERIAL_SEASONS` — у які сезони свіжий плід/ягода/овоч реально доступні в
Україні (за назвою сировини, як у seed.MATERIALS). Сировина, якої тут немає
(спеції, сушені-only, цитрусові й тропічні з цілорічним завозом), вважається
доступною цілий рік.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set

SEASON_SPRING = "spring"
SEASON_SUMMER = "summer"
SEASON_AUTUMN = "autumn"
SEASON_WINTER = "winter"
SEASONS_ORDER: List[str] = [
    SEASON_SPRING,
    SEASON_SUMMER,
    SEASON_AUTUMN,
    SEASON_WINTER,
]
SEASON_NAMES: Dict[str, str] = {
    SEASON_SPRING: "Весна",
    SEASON_SUMMER: "Літо",
    SEASON_AUTUMN: "Осінь",
    SEASON_WINTER: "Зима",
}

ALL = set(SEASONS_ORDER)
SPRING_SUMMER = {SEASON_SPRING, SEASON_SUMMER}
SUMMER_AUTUMN = {SEASON_SUMMER, SEASON_AUTUMN}
AUTUMN_WINTER = {SEASON_AUTUMN, SEASON_WINTER}

# Доступність СВІЖОЇ форми за сезонами. Ключ — точна назва сировини з seed.
MATERIAL_SEASONS: Dict[str, Set[str]] = {
    # --- Кісточкові та зерняткові ---
    "черешня": {SEASON_SUMMER},
    "вишня": {SEASON_SUMMER},
    "абрикос": {SEASON_SUMMER},
    "персик": {SEASON_SUMMER},
    "нектарин": {SEASON_SUMMER},
    "слива": {SEASON_AUTUMN},          # серпень–вересень (пізніша за полуницю)
    "яблуко": AUTUMN_WINTER,           # збір восени, зберігається до зими
    "яблуко зелене": AUTUMN_WINTER,
    "груша": SUMMER_AUTUMN,
    "айва": {SEASON_AUTUMN},
    "терен": {SEASON_AUTUMN},          # після перших заморозків
    "кизил": {SEASON_AUTUMN},
    "калина": AUTUMN_WINTER,           # після заморозків
    "хурма": AUTUMN_WINTER,
    "виноград": {SEASON_AUTUMN},
    "гранат": AUTUMN_WINTER,
    "інжир": SUMMER_AUTUMN,
    # --- Ягоди ---
    "полуниця": {SEASON_SUMMER},       # рання — початок літа
    "суниця": {SEASON_SUMMER},
    "малина": SUMMER_AUTUMN,
    "ожина": SUMMER_AUTUMN,
    "чорна смородина": {SEASON_SUMMER},
    "червона смородина": {SEASON_SUMMER},
    "аґрус": {SEASON_SUMMER},
    "ірга": {SEASON_SUMMER},
    "чорниця": {SEASON_SUMMER},
    "актинідія": {SEASON_AUTUMN},
    "брусниця": {SEASON_AUTUMN},
    "журавлина": AUTUMN_WINTER,
    "обліпина": {SEASON_AUTUMN},
    "горобина": {SEASON_AUTUMN},
    "чорноплідна горобина": {SEASON_AUTUMN},
    "глід": {SEASON_AUTUMN},
    "шипшина": {SEASON_AUTUMN},
    # --- Баштанні ---
    "диня": SUMMER_AUTUMN,
    "кавун": SUMMER_AUTUMN,
    # --- Овочі / зелень із вираженим сезоном свіжої форми ---
    "огірок": {SEASON_SUMMER},
    "томат": SUMMER_AUTUMN,
    "перець солодкий": SUMMER_AUTUMN,
    "ревінь": SPRING_SUMMER,           # квітень–червень
    "гарбуз": AUTUMN_WINTER,
}


def is_valid(season: Optional[str]) -> bool:
    return season in ALL


def season_name(season: Optional[str]) -> str:
    return SEASON_NAMES.get(season or "", "")


def fresh_in_season(material_name: str, season: Optional[str]) -> bool:
    """Чи доступна свіжа форма цієї сировини у заданий сезон.

    Якщо сезон не задано (None/невалідний) — сезонність не враховуємо (True).
    Сировина поза мапою вважається цілорічною (True).
    """
    if not is_valid(season):
        return True
    seasons = MATERIAL_SEASONS.get(material_name)
    if seasons is None:
        return True
    return season in seasons


def current_season(today: Optional[date] = None) -> str:
    """Сезон за поточною датою (північна півкуля)."""
    m = (today or date.today()).month
    if m in (3, 4, 5):
        return SEASON_SPRING
    if m in (6, 7, 8):
        return SEASON_SUMMER
    if m in (9, 10, 11):
        return SEASON_AUTUMN
    return SEASON_WINTER
