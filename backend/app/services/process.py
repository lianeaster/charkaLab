"""Технологічна карта рецепта: як готувати склад, який дібрав двигун.

Склад сам по собі ще не рецепт: плоду треба тижні, гвоздиці — дні, м'яті —
години, і одна банка «на три тижні для всього» перетягує зелень у гіркоту.
Тому час задається не рецептом, а КЛАСОМ сировини (частина рослини, форма,
гіркота), а рецепт складається з класів своїх інгредієнтів.

Це рівень «для дому»: орієнтири («2–3 тижні, пробувати з 10-го дня»), а не
точні режими. Точні параметри мають сенс лише для апаратних методів (вакуум,
ультразвук) — це наступний, лабораторний рівень (`level`).

Дома все настоюється в ОДНІЙ банці, але ступінчасто: кожен інгредієнт
закладається так, щоб закінчити разом з усіма (довгі — з першого дня, короткі —
наприкінці). Це дає різний час без окремих ємностей.

Звідки орієнтири (див. MACERATION_CLASSES, поле `basis`):
  - ВНТП 35-93: морс — дві заливки 45–50 % по 14 діб і пресування вичавок,
    ~90 % екстракту;
  - Sokół-Łętowska et al. 2018 (doi:10.3390/molecules23092156): вишня 1:1 на
    65 %, три тижні; Duplais 1866: малина 1:1, місяць;
  - мирт (Applied Sciences 2024): оптимум 20 діб при 25 °C, довше антоціани
    руйнуються;
  - лимонний лікер: основні сполуки цедри виходять за 24 год, мінорні — за
    3–4 доби, далі леткі монотерпени окиснюються й свіжість зникає;
  - фармакопейна мацерація настойок: 3 доби (USP) – 7 діб (BP), 1:5–1:10;
  - Ordine del Nocino Modenese: зелений горіх — проціджувати не раніше 60 діб;
  - холодна стабілізація −1 °C 24 год прибирає каламуть, не зачіпаючи
    альдегідів і терпенів (досліджено на абрикосовому бренді).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

from ..schemas import IngredientTiming, ProcessCard, ProcessStage


@dataclass(frozen=True)
class MacerationClass:
    title: str
    days: Tuple[float, float]  # орієнтир при кімнатній температурі
    prep: str = ""
    caution: str = ""
    basis: str = ""
    # «finishing» — не мацерується, а додається при купажі (сік, екстракт,
    # підсолоджувач); «macerate» — настоюється
    stage: str = "macerate"


MACERATION_CLASSES: Dict[str, MacerationClass] = {
    "fresh_fruit": MacerationClass(
        "свіжі плоди та ягоди", (14, 28),
        prep="Перебрати, помити й добре обсушити (вода розбавляє спирт і несе "
             "цвіль); великі плоди нарізати часточками.",
        basis="ВНТП 35-93 (морс: 2 заливки по 14 діб); вишня 1:1 — три тижні "
              "(Sokół-Łętowska 2018); мирт — оптимум 20 діб, довше антоціани руйнуються",
    ),
    "dried_fruit": MacerationClass(
        "сушені плоди", (14, 21),
        prep="Дрібні — цілими, великі — нарізати.",
        basis="як для свіжих плодів, але без соку, що розбавляє спирт",
    ),
    "green_walnut": MacerationClass(
        "зелений волоський горіх", (40, 60),
        prep="Збирати до Івана Купала, поки голкою проколюється наскрізь; "
             "різати на четвертинки в рукавичках (юглон фарбує шкіру).",
        basis="Ordine del Nocino Modenese — проціджувати не раніше 60 діб",
    ),
    "zest": MacerationClass(
        "цедра цитрусових", (1, 4),
        prep="Знімати овочечисткою смужками лише кольоровий шар — біле під ним "
             "гірчить. Не терти на тертці: дрібна стружка проходить крізь фільтр.",
        caution="Цедру довше 3–4 діб не тримати: леткі терпени окиснюються, "
                "свіжість іде, лишається гіркота.",
        basis="лимонний лікер: основні сполуки виходять за 24 год, мінорні — за 3–4 доби",
    ),
    "fresh_greens": MacerationClass(
        "свіжа зелень і квіти", (0.5, 2),
        prep="Брати лише листя чи квіти, без стебел, і класти цілими — не різати "
             "й не м'яти.",
        caution="Свіжа зелень за кілька діб дає трав'янисту гіркоту й буріє "
                "(окиснення хлорофілу) — краще недотримати, ніж перетримати.",
        basis="практика настоянок на м'яті; окиснення хлорофілу",
    ),
    "dry_herbs": MacerationClass(
        "сушені трави, листя й квіти", (2, 7),
        prep="Цілими або злегка розім'яти в руках — не молоти: порошок дає "
             "каламуть і погано фільтрується.",
        basis="фармакопейна мацерація: 3–7 діб",
    ),
    "bitter": MacerationClass(
        "гіркі трави, кора й корені", (1, 7),
        prep="Цілими або грубо поламати; дозувати скупо.",
        caution="Гіркоту пробувати щодня з першої доби: переекстракцію вже не "
                "виправити, лише розбавити.",
        basis="фармакопейна мацерація: 3–7 діб; гіркота наростає з часом",
    ),
    "hard_spice": MacerationClass(
        "тверді прянощі (насіння, кора, смоли)", (3, 7),
        prep="Злегка роздавити ступкою чи ножем плазом — олія в насінні "
             "всередині; не молоти в пил.",
        basis="фармакопейна мацерація: 3 (USP) – 7 (BP) діб",
    ),
    "root": MacerationClass(
        "сушені корені й кореневища", (7, 14),
        prep="Нарізати шматочками 3–5 мм — щільна тканина віддає повільно.",
        basis="щільна тканина віддає повільніше за насіння й листя",
    ),
    "pungent_fresh": MacerationClass(
        "гостра свіжа сировина", (1, 3),
        prep="Нарізати тонкими пластинками безпосередньо перед закладанням.",
        caution="Пекучість наростає швидко — пробувати вже за добу.",
        basis="практика хріновухи й перцівки",
    ),
    "vegetable": MacerationClass(
        "свіжі овочі", (1, 3),
        prep="Помити й нарізати кружальцями чи шматками.",
        caution="Свіжість овочів нестійка — за кілька діб тон стає «вареним».",
        basis="практика овочевих настоянок",
    ),
    "tea": MacerationClass(
        "чай і мате", (0.1, 1),
        caution="Довше доби чай дає терпкість танінів.",
        basis="екстракція танінів чаю наростає з часом",
    ),
    "coffee": MacerationClass(
        "кава", (1, 2),
        prep="Зерна грубого помелу або цілі злегка роздавлені.",
        caution="Понад 2 доби кава дає гіркоту.",
        basis="практика кавових лікерів",
    ),
    "vanilla": MacerationClass(
        "ваніль", (7, 14),
        prep="Стручок розрізати вздовж.",
        basis="практика ванільних настоянок",
    ),
    "nut": MacerationClass(
        "горіхи (ядро)", (7, 14),
        prep="Ядро злегка підсмажити до аромату, остудити й поламати — сирий "
             "горіх дає плаский тон.",
        basis="ключові ноти горіхів утворюються при смаженні (Burdack-Freitag 2012)",
    ),
    "juice": MacerationClass(
        "сік", (0, 0), stage="finishing",
        prep="Додати на етапі купажу, не мацерувати.",
    ),
    "extract": MacerationClass(
        "екстракт / ефірна олія", (0, 0), stage="finishing",
        prep="Додати на етапі купажу краплями, на смак.",
    ),
    "caramel": MacerationClass(
        "палений цукор", (0, 0), stage="finishing",
        prep="Розчинити в частині теплого настою на етапі купажу.",
    ),
    "sweetener": MacerationClass(
        "підсолоджувач", (0, 0), stage="finishing",
    ),
}

TEAS = {"зелений чай", "сенча", "мате", "лапсанг сушонг"}
VEGETABLES = {
    "огірок", "морква", "буряк столовий", "томат", "перець солодкий",
    "селера стеблова", "селера (корінь)", "ревінь", "гарбуз",
}
SWEETENERS = {"цукор", "мед"}
NUTS = {"фундук", "мигдаль"}
# прянощі поза таблицею SPICES: сухі «ягоди» й «боби», що поводяться як спеції
SPICE_LIKE_EXTRA = {"кубеба", "рожевий перець", "боби тонка"}
FRESH_NOTES = {"свіжий", "зелений", "м'ятний", "ментоловий", "охолоджуючий"}
# сполуки анісової групи, що мутніють при розведенні (як узо чи пастис);
# цитрусову олію ловимо за класом «цедра» — лімонен є в надто багатьох рослинах
CLOUDING_COMPOUNDS = {"анетол", "естрагол", "Фенхон"}
# Гірка трава — трава, лист, корінь чи кора, де гіркота (або в'язка
# терпкість, як у дубової кори) головна. Насіння й квіти сюди не йдуть: у
# айовану, какао чи шафрану гіркота є, але настоюються вони як прянощі.
BITTER_TASTE_MIN = 0.55
ASTRINGENT_TASTE_MIN = 1.0
BITTER_PARTS = ("herb", "leaf", "root", "rhizome", "bark")
PUNGENT_TASTE_MIN = 0.5


# --- як різати й що брати -------------------------------------------------
# Загальне правило: різати чи давити лише те, де аромат усередині тканини
# (насіння, корені, щільні ягоди, великі плоди). Листя губоцвітих (м'ята,
# меліса, базилік…) тримає ефірну олію в залозках НА ПОВЕРХНІ листка — спирт
# бере її й з цілого листка, а різання додає лише хлорофіл і трав'янистий тон
# скошеної трави (ушкоджені клітини запускають утворення зелених альдегідів).
LAMIACEAE_SOFT = {
    "м'ята перечна", "м'ята кучерява", "меліса", "базилік", "шавлія",
    "іссоп", "лофант анісовий",
}
WOODY_HERBS = {"розмарин", "чебрець (тим'ян)", "чабер", "душиця (орегано)", "майоран"}
STONE_FRUIT = {"вишня", "черешня", "слива", "абрикос", "персик", "нектарин", "кизил", "терен"}
POME_FRUIT = {"яблуко", "яблуко зелене", "груша", "айва"}
DENSE_BERRIES = {
    "журавлина", "брусниця", "чорноплідна горобина", "горобина", "калина",
    "глід", "барбарис", "обліпина",
}
TROPICAL = {"ананас", "манго", "банан", "папайя", "ківі", "маракуйя", "личі", "хурма", "інжир"}

LEAF_PREP = (
    "Лише листя, без стебел, і цілим — не різати й не м'яти: олія сидить у "
    "залозках на поверхні листка, а різання додає хлорофіл і гіркуватий тон "
    "скошеної трави."
)
WOODY_PREP = (
    "Гілочки цілими або обібране листя; здерев'янілі стебла не класти — гірчать."
)
FLOWER_PREP = "Лише квіти чи пелюстки, без зелених частин; цілими, не різати."

# Особливості конкретної сировини: (назва, частина) або назва → як готувати.
PREP_BY_NAME: Dict[object, str] = {
    ("троянда чайна", "flower"): (
        "Лише пелюстки, без чашолистків; білу основу пелюстки відщипнути — "
        "вона гірчить. Не різати."
    ),
    ("бузина чорна", "flower"): (
        "Квіточки зрізати з зелених ніжок: ніжки гіркі й містять ціаногенний "
        "глікозид. Не мити — аромат дає пилок; лише струсити комах."
    ),
    ("бузина чорна", "berry"): (
        "Лише стиглі ягоди без гілочок і ніжок (зелені частини містять "
        "ціаногенний глікозид)."
    ),
    ("липа", "flower"): "Суцвіття разом із приквітком, як для чаю; цілими.",
    ("лаванда", "flower"): "Лише квіткові колоски без стебел, цілими.",
    ("ромашка", "flower"): "Цілі кошики квітів без стебел.",
    ("акація біла", "flower"): "Лише квіти без ніжок і зелених чашечок; цілими.",
    ("хміль", "flower"): "Шишки цілими.",
    ("шафран", "flower"): "Приймочки цілими.",
    ("гвоздика", "flower"): "Бутони цілими.",
    "лавровий лист": "Цілими або розламати навпіл.",
    "кардамон": "Коробочки надломити, щоб відкрилось насіння.",
    "мускатний горіх": (
        "Розколоти на кілька шматків — тертий віддає надто різко й каламутить."
    ),
    "бадьян": "Зірочки цілими.",
    "кориця цейлонська": "Палички поламати на шматки.",
    "кассія (китайська кориця)": "Кору поламати на шматки.",
    "ялівець": "Ягоди злегка роздавити.",
    "шипшина": (
        "Розрізати й вичистити насіння з волосками — волоски подразнюють "
        "горло; настій потім ретельно фільтрувати."
    ),
    "виноград": "Ягоди зняти з гребенів (гребені терпкі), злегка надавити.",
    ("імбир", "rhizome"): (
        "Тонкими пластинками, не терти: тертий дає різку пекучість і каламуть."
    ),
    "червоний гострий перець": (
        "Розрізати вздовж; насіння й перетинки — головне джерело пекучості: "
        "прибрати, щоб вийшло м'якше."
    ),
    "часник": "Зубчики розрізати навпіл.",
    "огірок": "Кружальцями разом зі шкіркою — у ній більшість аромату.",
    "лемонграс": (
        "Стебла порізати шматками 2–3 см і злегка відбити — це злак, олія в "
        "нього всередині волокнистого стебла, а не на поверхні."
    ),
}


def prep_for(item: "ProcessItem", cls: str) -> str:
    """Як готувати конкретний інгредієнт перед закладанням."""
    name, part = item.name, item.part
    for key in ((name, part), name):
        if key in PREP_BY_NAME:
            return PREP_BY_NAME[key]
    if cls in ("fresh_greens", "dry_herbs", "bitter") and part in ("leaf", "herb"):
        if name in WOODY_HERBS:
            return WOODY_PREP
        if name in LAMIACEAE_SOFT or cls == "fresh_greens":
            return LEAF_PREP
    if cls in ("fresh_greens", "dry_herbs") and part == "flower":
        return FLOWER_PREP
    if cls == "dried_fruit":
        if part == "berry":
            return "Цілими або злегка розім'яти."
        return "Нарізати шматочками."
    if cls == "fresh_fruit":
        if name in STONE_FRUIT:
            if item.pit == "with":
                return "Цілими з кісточкою; помити й добре обсушити."
            return "Вийняти кісточки; великі плоди — половинками."
        if name in POME_FRUIT:
            return (
                "Нарізати часточками й вирізати серцевину з насінням — у насінні "
                "яблук і айви теж є амигдалін."
            )
        if name in DENSE_BERRIES:
            return (
                "Цілими, але наколоти чи злегка надавити — щільна шкірка не "
                "пускає спирт усередину."
            )
        if name in TROPICAL:
            return "Очистити й нарізати шматками."
        if part == "berry":
            return "Перебрати, обсушити й класти цілими — ніжні ягоди не давити."
    return MACERATION_CLASSES[cls].prep


@dataclass
class ProcessItem:
    """Інгредієнт складу з тим, що двигун знає про його варіант."""

    name: str
    part: str
    form: str
    pit: str
    role: str
    chans: Dict[str, float]
    compounds: Set[str]


def classify(item: ProcessItem, spice_names: Set[str]) -> str:
    """Клас мацерації інгредієнта (ключ MACERATION_CLASSES)."""
    name, part, form = item.name, item.part, item.form
    if item.role == "sweetener" or name in SWEETENERS:
        return "sweetener"
    if name == "палений цукор":
        return "caramel"
    if form == "juice":
        return "juice"
    if form in ("extract", "oil"):
        return "extract"
    if name in TEAS:
        return "tea"
    if name == "кава":
        return "coffee"
    if name == "ваніль":
        return "vanilla"
    if name == "волоський горіх" and part == "fruit":
        return "green_walnut"
    if name in NUTS or (name == "волоський горіх" and part == "seed"):
        return "nut"
    if name in VEGETABLES and form == "fresh":
        return "vegetable"
    bitter = item.chans.get("taste::гіркий", 0.0)
    astringent = item.chans.get("taste::терпкий", 0.0)
    # в імбиру чи перцю гіркота теж є, але поступається пекучості
    if (
        part in BITTER_PARTS
        and (bitter >= BITTER_TASTE_MIN or astringent >= ASTRINGENT_TASTE_MIN)
        and bitter >= item.chans.get("taste::пекучий", 0.0)
    ):
        return "bitter"
    if part == "zest":
        return "zest"
    if part in ("leaf", "herb", "flower", "needle"):
        return "fresh_greens" if form == "fresh" else "dry_herbs"
    is_spice = name in spice_names or name in SPICE_LIKE_EXTRA
    if form == "fresh" and (
        part == "bulb"  # часник: гострота в сірчаних сполуках аромату, не в смаку
        or item.chans.get("taste::пекучий", 0.0) >= PUNGENT_TASTE_MIN
    ):
        return "pungent_fresh"
    if form == "fresh" and is_spice:
        # свіже зелене насіння коріандру чи кропу — ніжне, як зелень
        return "fresh_greens"
    if part in ("root", "rhizome"):
        return "pungent_fresh" if form == "fresh" else "root"
    if part in ("seed", "bark", "resin"):
        return "hard_spice"
    if form == "fresh":
        return "fresh_fruit"
    return "hard_spice" if is_spice else "dried_fruit"


# --- домашні методи ------------------------------------------------------
@dataclass(frozen=True)
class HomeMethod:
    title: str
    temperature: str
    factor: float  # множник часу відносно кімнатної температури
    why: str


METHODS: Dict[str, HomeMethod] = {
    "classic": HomeMethod(
        "Класична мацерація", "18–22 °C, темне місце", 1.0,
        "Найпростіший і передбачуваний режим без обладнання.",
    ),
    "cold": HomeMethod(
        "Холодна мацерація", "4–8 °C, холодильник", 1.5,
        "У профілі свіжі ноти, а їх дають найлеткіші сполуки — у холоді вони "
        "менше окиснюються й не вивітрюються. Платою є довший час.",
    ),
    "gradient": HomeMethod(
        "Градієнтна мацерація",
        "перші 3 доби — холодильник 4–8 °C, далі 18–22 °C, останні 3–4 доби — "
        "тепло 26–28 °C",
        1.0,
        "Основа — свіжі плоди: холодний старт береже леткі ноти, а теплий фініш "
        "прискорює гідроліз зв'язаних форм аромату (глікозидів), яких у плоді "
        "більше, ніж вільних.",
    ),
    "wine": HomeMethod(
        "Мацерація у вині", "8–12 °C, ємність під горло", 0.5,
        "Вино окиснюється значно швидше за спирт і екстрагує ефірні олії слабше — "
        "коротко й у холоді.",
    ),
    "nonalc": HomeMethod(
        "Безалкогольна інфузія", "холодильник 4–6 °C", 0.0,
        "Без спирту настій мікробіологічно нестійкий: лише холод і години, а не дні.",
    ),
}


def _choose_method(
    base_abv: Optional[int], main_class: str, desired: Sequence[str], main_pit: str,
) -> str:
    """base_abv None — основу не обрано: вважаємо її спиртом."""
    if base_abv is not None and base_abv <= 0:
        return "nonalc"
    if base_abv is not None and base_abv < 20:
        return "wine"
    fresh_wanted = bool(FRESH_NOTES & set(desired))
    if fresh_wanted and main_class in ("fresh_fruit", "fresh_greens", "vegetable", "zest"):
        return "cold"
    # теплий фініш градієнта з цілою кісточкою — це більше амигдаліну в настої
    if main_class == "fresh_fruit" and main_pit != "with":
        return "gradient"
    return "classic"


def _fmt_days(value: float) -> str:
    if value < 1:
        return f"{max(1, round(value * 24))} год"
    v = round(value)
    if v % 10 == 1 and v % 100 != 11:
        word = "доба"
    elif v % 10 in (2, 3, 4) and v % 100 not in (12, 13, 14):
        word = "доби"
    else:
        word = "діб"
    return f"{v} {word}"


def _fmt_range(lo: float, hi: float) -> str:
    if hi < 1:
        return f"{max(1, round(lo * 24))}–{round(hi * 24)} год"
    if lo < 1:
        return f"{max(1, round(lo * 24))} год – {_fmt_days(hi)}"
    return f"{round(lo)}–{_fmt_days(hi)}"


def build(
    items: List[ProcessItem],
    base_name: Optional[str],
    base_abv: Optional[int],
    desired: Sequence[str],
    spice_names: Set[str],
) -> ProcessCard:
    """Технологічна карта для домашнього рівня.

    base_abv — міцність основи; None, коли основу не обрано (тоді — спирт)."""
    classified = [(it, classify(it, spice_names)) for it in items]
    main = next((pair for pair in classified if pair[0].role == "main"), None)
    main_class = main[1] if main else "hard_spice"
    main_pit = main[0].pit if main else "na"
    method_key = _choose_method(base_abv, main_class, desired, main_pit)
    method = METHODS[method_key]

    macerated = [
        (it, cls) for it, cls in classified
        if MACERATION_CLASSES[cls].stage == "macerate"
    ]
    finishing = [
        (it, cls) for it, cls in classified
        if MACERATION_CLASSES[cls].stage == "finishing"
    ]
    classes_present = {cls for _it, cls in classified}

    stages: List[ProcessStage] = []
    cautions: List[str] = []
    schedule: List[IngredientTiming] = []

    # --- 1. підготовка ---------------------------------------------------
    # одна порада — один рядок; інгредієнти з однаковою підготовкою разом
    prep_groups: Dict[str, List[str]] = {}
    for it, cls in classified:
        if MACERATION_CLASSES[cls].stage != "macerate":
            continue
        text = prep_for(it, cls)
        if text:
            prep_groups.setdefault(text, [])
            if it.name not in prep_groups[text]:
                prep_groups[text].append(it.name)
    prep: List[str] = [
        f"{', '.join(names).capitalize()}: {text[0].lower() + text[1:]}"
        for text, names in prep_groups.items()
    ]
    if any(it.pit == "with" for it, _ in classified):
        prep.append(
            "Кісточки лишати ЦІЛИМИ: подрібнене ядро швидко вивільняє з амигдаліну "
            "синильну кислоту. Ціла кісточка дає м'який мигдальний тон поступово."
        )
        cautions.append(
            "Плоди з кісточкою не тримати місяцями й не в теплі: що довше й "
            "тепліше, то більше амигдаліну переходить з ядра."
        )
    if main_class == "fresh_fruit" and method_key not in ("nonalc", "wine"):
        prep.append(
            "Можна заморозити плоди на добу при −18 °C: кристали льоду рвуть "
            "клітини, і настій екстрагується повніше (у вина це давало помітно "
            "більше вільних терпенів). Час мацерації тоді — приблизно на третину менший."
        )
    stages.append(ProcessStage(key="prep", title="Підготовка сировини", steps=prep))

    # --- 2. мацерація: графік закладання в одну банку --------------------
    if method_key == "nonalc":
        total_days = "12–24 год"
        hot = [it.name for it, cls in macerated if cls in (
            "hard_spice", "root", "bitter", "dry_herbs", "coffee", "vanilla", "nut",
        )]
        steps = [
            "Свіжу сировину залити холодною основою й поставити в холодильник на 12–24 год.",
        ]
        if hot:
            steps.append(
                f"Сухе й тверде ({', '.join(hot)}) спершу заварити в частині води "
                "при 85–95 °C 5–10 хв, остудити й лише тоді додати — у холодній "
                "воді воно майже не віддає аромату."
            )
        if base_name and "газован" in base_name:
            steps.insert(0, (
                "Газовану воду не настоювати — газ вийде. Інфузію робити в "
                "негазованій воді чи сиропі, а газовану доливати перед подачею."
            ))
        steps.append("Тримати в холодильнику й випити за 3–5 днів.")
        for it, cls in macerated:
            schedule.append(IngredientTiming(
                name=it.name, class_title=MACERATION_CLASSES[cls].title,
                duration="12–24 год", start="з початку",
            ))
        stages.append(ProcessStage(key="maceration", title=method.title, steps=steps))
        cautions.append("Без спирту настій псується: лише холодильник і кілька днів.")
    else:
        durations: List[Tuple[ProcessItem, str, float, float, float]] = []
        for it, cls in macerated:
            lo, hi = MACERATION_CLASSES[cls].days
            lo, hi = lo * method.factor, hi * method.factor
            if method_key == "wine":
                hi = min(hi, 14.0)
                lo = min(lo, hi)
            durations.append((it, cls, lo, hi, (lo + hi) / 2))
        total = max((d[4] for d in durations), default=0.0)
        total_days = _fmt_days(total) if total else "—"
        for it, cls, lo, hi, mid in sorted(durations, key=lambda d: -d[4]):
            start = total - mid
            if mid >= total - 0.5:
                start_text = "з першого дня"
            elif mid < 1:
                start_text = f"за ~{_fmt_days(mid)} до зняття"
            else:
                start_text = f"на {round(start) + 1}-й день"
            schedule.append(IngredientTiming(
                name=it.name,
                class_title=MACERATION_CLASSES[cls].title,
                duration=_fmt_range(lo, hi),
                start=start_text,
                taste_from=(
                    f"пробувати з {max(1, round(start + lo))}-го дня"
                    if lo >= 1 else ""
                ),
            ))
        if method_key != "wine":
            if main_class in ("fresh_fruit", "vegetable"):
                abv = ("Залити спиртом 60–70 %: сік плодів розбавить його до 45–50 %, "
                       "з якими працює класична технологія морсів.")
            elif main_class in ("zest", "fresh_greens"):
                abv = "Залити міцним спиртом 70–96 %: коротка інтенсивна екстракція."
            else:
                abv = "Залити спиртом 45–60 %."
        else:
            abv = "Залити вином під горло, щоб над рідиною лишалось якомога менше повітря."
        steps = [
            abv,
            "Скляна банка, заповнена майже під горло (менше повітря — менше "
            "окиснення), щільна кришка, без прямого світла.",
            "Струшувати щодня перший тиждень, далі — раз на 2–3 дні.",
        ]
        if len(durations) > 1:
            steps.append(
                "Довгі інгредієнти закладаються першими, короткі — пізніше, щоб усі "
                "закінчили разом (графік нижче)."
            )
            mids = [d[4] for d in durations]
            if max(mids) >= 10 * max(min(mids), 0.1):
                steps.append(
                    "Якщо незручно додавати по черзі — настійте короткі інгредієнти "
                    "окремо в малій банці й змішайте настої на купажі."
                )
        stages.append(ProcessStage(key="maceration", title=method.title, steps=steps))

    for _it, cls in classified:
        text = MACERATION_CLASSES[cls].caution
        if text and text not in cautions:
            cautions.append(text)

    # --- 3. зняття настою -------------------------------------------------
    fruit_main = main_class in ("fresh_fruit", "dried_fruit", "green_walnut")
    fruit_like = classes_present & {"fresh_fruit", "dried_fruit", "green_walnut", "vegetable"}
    if fruit_main and method_key == "wine":
        separation = [
            "Злити вино, плоди віджати через марлю.",
            "Відстояти добу в холоді, злити з осаду й профільтрувати.",
        ]
    elif fruit_main and method_key != "nonalc":
        separation = [
            "Злити настій, сировину віджати через марлю чи прес — у вичавках "
            "лишається чимала частка екстракту.",
            "Опційно: залити вичавки ще раз свіжим спиртом на ~14 діб і так само "
            "віджати — дві заливки з пресуванням вилучають близько 90 % екстракту "
            "(ВНТП 35-93).",
            "Відстояти 1–3 доби в холоді, обережно злити з осаду й профільтрувати "
            "(вата з марлею або паперовий фільтр).",
        ]
    elif fruit_like and method_key != "nonalc":
        separation = [
            "Злити настій, плоди й овочі віджати через марлю.",
            "Відстояти добу в холоді, злити з осаду й профільтрувати (вата або паперовий фільтр).",
        ]
    else:
        separation = [
            "Процідити через сито з марлею, потім профільтрувати (вата або паперовий фільтр).",
        ]
    stages.append(ProcessStage(key="separation", title="Зняття й фільтрація", steps=separation))

    # --- 4. купаж і корекція ----------------------------------------------
    finishing_steps: List[str] = []
    late = [it.name for it, cls in finishing if cls in ("juice", "extract", "caramel")]
    if late:
        finishing_steps.append(f"Додати на цьому етапі: {', '.join(late)}.")
    sweeteners = [it.name for it, cls in finishing if cls == "sweetener"]
    if sweeteners:
        if "мед" in sweeteners:
            finishing_steps.append(
                "Мед розвести невеликою кількістю теплої (не гарячої) води й "
                "вмішувати поступово, пробуючи."
            )
        else:
            finishing_steps.append(
                "Підсолоджувати сиропом (цукор, розчинений у частині води), а не "
                "сухим цукром — рівномірніше і без осаду."
            )
    if method_key != "nonalc":
        finishing_steps.append(
            "Довести водою чи сиропом до бажаної міцності. Після змішування об'єм "
            "трохи зменшується (контракція) — фінальну міцність міряти після відпочинку."
        )
    clouding = any(
        it.compounds & CLOUDING_COMPOUNDS for it, _cls in macerated
    ) or "zest" in classes_present
    if clouding and method_key != "nonalc":
        finishing_steps.append(
            "Розводити поступово, краще сиропом: ефірні олії цитрусу й анісу при "
            "зниженні міцності дають помутніння."
        )
    if finishing_steps:
        stages.append(ProcessStage(key="finishing", title="Купаж і корекція", steps=finishing_steps))

    # --- 5. стабілізація й відпочинок ------------------------------------
    if method_key != "nonalc":
        stages.append(ProcessStage(
            key="stabilization", title="Стабілізація (за бажання)", steps=[
                "Витримати добу в холоді (−1…+4 °C) і профільтрувати холодним: осад, "
                "що інакше випав би в пляшці, лишиться на фільтрі. Альдегіди й "
                "терпени аромату при цьому не страждають.",
            ],
        ))
        if method_key == "wine":
            rest = ("1–2 тижні в холоді. Ароматизоване вино не для довгого "
                    "зберігання: відкриту пляшку — у холодильник і випити за тиждень.")
        elif main_class in ("fresh_fruit", "dried_fruit", "green_walnut"):
            rest = "1–3 місяці в темряві: фруктові настоянки з часом округлюються."
        else:
            rest = "2–4 тижні в темряві, щоб смак «зібрався»."
        stages.append(ProcessStage(key="rest", title="Відпочинок", steps=[rest]))

    basis = sorted({
        MACERATION_CLASSES[cls].basis for _it, cls in classified
        if MACERATION_CLASSES[cls].basis
    })
    method_note = method.why
    if method_key == "classic" and main_class == "fresh_fruit" and main_pit == "with":
        method_note = (
            "Плоди з кісточкою — без теплої фази градієнта: тепло прискорює "
            "перехід амигдаліну з ядра."
        )
    return ProcessCard(
        level="home",
        method=method.title,
        method_note=method_note,
        temperature=method.temperature,
        total_time=total_days,
        schedule=schedule,
        stages=stages,
        cautions=cautions,
        basis=basis,
    )
