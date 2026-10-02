# dataclasses: памятка

02.10.2026. Оригинал (Claude Docs, можно выгрузить в PDF): https://claude.ai/code/artifact/db4471b7-7c82-4229-a2af-03a9e675c8e2

Стандартная библиотека, ничего ставить не нужно. Python 3.10+.

## 1. Объявление и поля

`@dataclass` пишет за тебя `__init__`, `__repr__` и `__eq__`. Поле - атрибут класса с аннотацией типа. Атрибут без аннотации - обычный атрибут класса, не поле и не ошибка.

```python
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Promo:
    code: str                                   # обязательное
    value: Decimal                              # обязательное
    max_discount: Decimal | None = None         # необязательное
    tags: list[str] = field(default_factory=list)

    currency = "RUB"                            # без аннотации - атрибут класса


p = Promo("A", Decimal("5"))                  # позиционно можно
p = Promo(code="A", value=Decimal("5"))      # и по имени
print(p)          # Promo(code='A', value=Decimal('5'), max_discount=None, tags=[])
```

- Поля без значения по умолчанию идут раньше полей со значением. Иначе `TypeError: non-default argument follows default argument`. Обход - `kw_only=True` (раздел 2).
- Изменяемое значение по умолчанию (`list`, `dict`, `set`) - только через `field(default_factory=list)`. `tags: list[str] = []` даст `ValueError` при объявлении класса.
- Аннотации не проверяются: `Promo(code=1, value="x")` создастся. Проверки пишутся вручную в `__post_init__` (раздел 4).
- Атрибут класса можно и с аннотацией: `currency: ClassVar[str] = "RUB"`. Для dataclass это необязательно.

## 2. Параметры декоратора

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class Promo:
    code: str
    value: Decimal
```

| Параметр | Что делает |
| --- | --- |
| `frozen=True` | присваивание полю - `FrozenInstanceError`; объект хешируемый: можно в set и ключом dict |
| `slots=True` | `__slots__`: меньше памяти, быстрее доступ, опечатка `p.vlaue = 1` - ошибка |
| `kw_only=True` | все аргументы только по имени; снимает правило порядка полей с умолчанием |
| `order=True` | сравнение `<`, `>` по полям по порядку, как у кортежей; можно сортировать |
| `eq=False` | не генерировать `__eq__`: объекты равны, только если это один объект |
| `repr=False` | не генерировать `__repr__` |

- По умолчанию (`eq=True`, `frozen=False`) объект не хешируется: `{p}` даст `TypeError: unhashable type`.
- Для доменных значений (деньги, промокод, координаты) хороший выбор по умолчанию - `frozen=True, slots=True`.
- Для объекта со состоянием (счетчик использований, корзина) - обычный `@dataclass` или обычный класс.
- С `slots=True` декоратор создает новый класс. `super()` без аргументов в методах такого класса ломается (проверено на Python 3.12); обход - `super(Child, self)`.

## 3. field(): настройка одного поля

```python
from dataclasses import dataclass, field


@dataclass
class PromoUsage:
    code: str
    used_by: dict[int, int] = field(default_factory=dict)   # user_id -> число использований
    total: int = field(default=0, init=False)               # не в __init__, считаем сами
    secret: str = field(default="", repr=False)             # не печатать в repr
    note: str = field(default="", compare=False)            # не учитывать в ==
```

| Аргумент | Зачем |
| --- | --- |
| `default=` | значение по умолчанию, если нужны еще аргументы `field` |
| `default_factory=` | функция без аргументов, вызывается для каждого объекта: `list`, `dict`, `set`, `lambda: ["x"]`, `datetime.now` |
| `init=False` | поля нет в конструкторе; задается по умолчанию или в `__post_init__` |
| `repr=False` | прячет поле из `repr` (пароли, токены, большие списки) |
| `compare=False` | поле не участвует в `==`, `<` и хеше |
| `kw_only=True` | только это поле - только по имени |

`default=` и `default_factory=` вместе указывать нельзя.

## 4. `__post_init__`: проверки и вычисляемые поля

`__post_init__` вызывается сразу после сгенерированного `__init__`. Здесь проверяют данные, нормализуют их и считают поля с `init=False`.

```python
from dataclasses import InitVar, dataclass, field


@dataclass(frozen=True)
class Promo:
    code: str
    percent: Decimal

    def __post_init__(self):
        if not 0 < self.percent <= 100:
            raise ValueError(f"percent must be in (0, 100], got {self.percent}")
        # frozen: self.code = ... нельзя, только так:
        object.__setattr__(self, "code", self.code.strip().upper())


@dataclass
class Trip:
    price: Decimal
    discount: Decimal = Decimal("0")
    total: Decimal = field(init=False)
    surge: InitVar[Decimal] = Decimal("1")      # аргумент __init__, но не поле

    def __post_init__(self, surge: Decimal):
        self.total = self.price * surge - self.discount
```

- Ошибки проверки - своим исключением или `ValueError` с понятным текстом. В тесте: `with pytest.raises(ValueError, match="percent"):`.
- `InitVar[T]` - значение приходит в конструктор и передается в `__post_init__` аргументом, но в объекте не хранится.
- Вычисляемое значение, которое должно меняться вместе с полями, проще сделать `@property`: оно не устареет.

## 5. Функции модуля

```python
from dataclasses import asdict, astuple, fields, is_dataclass, replace

p = Promo(code="a", percent=Decimal("10"))

asdict(p)         # {'code': 'A', 'percent': Decimal('10')} - рекурсивно, вложенные тоже
astuple(p)        # ('A', Decimal('10'))
p2 = replace(p, percent=Decimal("20"))   # копия с изменением, __post_init__ снова вызовется
[f.name for f in fields(p)]              # ['code', 'percent']
is_dataclass(p)   # True
```

- `replace` - главный способ "изменить" frozen-объект: он создает новый через `__init__`, поэтому проверки сработают. Поле с `init=False` передать в `replace` нельзя.
- `asdict` не превращает Decimal и datetime в строки. Для JSON: `json.dumps(asdict(p), default=str)`.
- `asdict` делает глубокую копию и недешев на больших объектах.

## 6. Наследование и абстрактные классы

Общие поля и абстрактный метод - в базе, свои поля и расчет - в наследниках. Константа типа пишется без аннотации и без `ClassVar`: для dataclass это просто атрибут класса.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class PromoType(StrEnum):
    PERCENT = "percent"
    FIX = "fix"


@dataclass(frozen=True, kw_only=True)
class PromoCodeBase(ABC):
    code: str
    valid_until: datetime
    min_order: Decimal = Decimal("0")

    @abstractmethod
    def discount(self, price: Decimal) -> Decimal: ...


@dataclass(frozen=True, kw_only=True)
class PromoCodePercent(PromoCodeBase):
    promo_type = PromoType.PERCENT        # константа класса, не поле
    percent: Decimal
    max_discount: Decimal | None = None

    def discount(self, price: Decimal) -> Decimal:
        d = price * self.percent / 100
        return min(d, self.max_discount) if self.max_discount is not None else d


@dataclass(frozen=True, kw_only=True)
class PromoCodeFix(PromoCodeBase):
    promo_type = PromoType.FIX
    amount: Decimal

    def discount(self, price: Decimal) -> Decimal:
        return min(self.amount, price)
```

- `@dataclass` нужен на каждом наследнике. Без него аннотации наследника не станут полями и не попадут в `__init__`.
- Поля базы идут в `__init__` первыми. Если в базе есть поле со значением, а в наследнике без - `TypeError` о порядке аргументов. `kw_only=True` на всех классах избавляет от этой проблемы.
- У frozen-базы наследники тоже должны быть frozen, и наоборот. Иначе `TypeError`.
- `PromoCodeBase(...)` напрямую создать нельзя: `TypeError: Can't instantiate abstract class`.
- Константа читается и у класса, и у объекта: `PromoCodeFix.promo_type`, `promo.promo_type`.

## 7. Типичные ошибки и отличия от pydantic

| Ошибка | Как правильно |
| --- | --- |
| `tags: list[str] = []` | `tags: list[str] = field(default_factory=list)` |
| `field(default=[])` | `field(default_factory=list)` |
| поле без умолчания после поля со умолчанием | поменять порядок или `kw_only=True` |
| `self.x = ...` в `__post_init__` frozen-класса | `object.__setattr__(self, "x", ...)` |
| ждать ошибку на неверный тип | типы не проверяются - писать проверки в `__post_init__` |
| класть обычный dataclass в set или ключом dict | `frozen=True` |
| наследник без `@dataclass` | декоратор на каждом классе с новыми полями |
| `==` сравнивает служебное поле | `field(compare=False)` |

|  | dataclass | pydantic |
| --- | --- | --- |
| Установка | стандартная библиотека | `pip install pydantic` |
| Проверка и приведение типов | нет, вручную в `__post_init__` | да, при создании |
| Позиционные аргументы | да | нет |
| Атрибут без аннотации | атрибут класса | ошибка, нужен `ClassVar` |
| `= []` по умолчанию | ошибка | можно |
| Копия с изменением | `replace(p, x=1)` | `p.model_copy(update={"x": 1})` |
| В dict | `asdict(p)` | `p.model_dump()` |
| JSON | вручную через `json` | `p.model_dump_json()`, `model_validate_json` |

На собеседовании dataclass - хороший выбор для доменных объектов: ничего ставить не нужно, и он показывает знание стандартной библиотеки. Pydantic уместен, когда данные приходят сырыми: JSON, запрос API, конфиг.

Справка: [docs.python.org/3/library/dataclasses](https://docs.python.org/3/library/dataclasses.html).
