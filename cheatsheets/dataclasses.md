# dataclasses: памятка

Стандартная библиотека, Python 3.10+.

## Объявление

```python
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Promo:
    code: str                                   # обязательное
    value: Decimal
    max_discount: Decimal | None = None         # необязательное
    tags: list[str] = field(default_factory=list)
    currency = "RUB"                            # без аннотации - атрибут класса


Promo("A", Decimal("5"))                         # позиционно можно
Promo(code="A", value=Decimal("5"))
```

- Поля без умолчания идут раньше полей с умолчанием, иначе `TypeError`. Обход - `kw_only=True`.
- `tags: list[str] = []` - `ValueError`; изменяемое умолчание только через `default_factory`.
- Типы не проверяются: `Promo(code=1, value="x")` создастся. Проверки - в `__post_init__`.

## Параметры декоратора

`@dataclass(frozen=True, slots=True, kw_only=True)`

| Параметр | Что делает |
| --- | --- |
| `frozen=True` | присваивание - `FrozenInstanceError`; объект хешируемый |
| `slots=True` | меньше памяти; опечатка `p.vlaue = 1` - ошибка |
| `kw_only=True` | аргументы только по имени |
| `order=True` | сравнение `<` `>` по полям по порядку, сортировка |
| `eq=False` | равенство по идентичности объекта |

- По умолчанию объект не хешируется: `{p}` - `TypeError`.
- С `slots=True` `super()` без аргументов ломается (3.12); обход - `super(Child, self)`.

## field()

```python
@dataclass
class PromoUsage:
    code: str
    used_by: dict[int, int] = field(default_factory=dict)
    total: int = field(default=0, init=False)          # не в __init__
    secret: str = field(default="", repr=False)        # не в repr
    note: str = field(default="", compare=False)       # не в == и хеше
```

`kw_only=True` - только это поле по имени. `default` и `default_factory` вместе нельзя.

## `__post_init__`

```python
from dataclasses import InitVar


@dataclass(frozen=True)
class Promo:
    code: str
    percent: Decimal

    def __post_init__(self):
        if not 0 < self.percent <= 100:
            raise ValueError(f"percent must be in (0, 100], got {self.percent}")
        object.__setattr__(self, "code", self.code.strip().upper())   # frozen: только так


@dataclass
class Trip:
    price: Decimal
    total: Decimal = field(init=False)
    surge: InitVar[Decimal] = Decimal("1")             # аргумент __init__, не поле

    def __post_init__(self, surge: Decimal):
        self.total = self.price * surge
```

Значение, зависящее от полей, проще сделать `@property`.

## Функции модуля

```python
from dataclasses import asdict, astuple, fields, is_dataclass, replace

asdict(p)                                  # {'code': 'A', 'percent': Decimal('10')}, рекурсивно
astuple(p)                                 # ('A', Decimal('10'))
replace(p, percent=Decimal("20"))          # копия через __init__: __post_init__ сработает
[f.name for f in fields(p)]                # ['code', 'percent']
is_dataclass(p)                            # True
json.dumps(asdict(p), default=str)         # в JSON
```

Поле с `init=False` в `replace` передать нельзя.

## Наследование и абстрактный класс

```python
from abc import ABC, abstractmethod
from enum import StrEnum


class PromoType(StrEnum):
    PERCENT = "percent"
    FIX = "fix"


@dataclass(frozen=True, kw_only=True)
class PromoCodeBase(ABC):
    code: str
    min_order: Decimal = Decimal("0")

    @abstractmethod
    def discount(self, price: Decimal) -> Decimal: ...


@dataclass(frozen=True, kw_only=True)
class PromoCodeFix(PromoCodeBase):
    promo_type = PromoType.FIX                 # константа класса
    amount: Decimal

    def discount(self, price: Decimal) -> Decimal:
        return min(self.amount, price)
```

- `@dataclass` на каждом наследнике, иначе его поля не попадут в `__init__`.
- Поле со значением в базе и без значения в наследнике - `TypeError`; `kw_only=True` решает.
- Frozen и не frozen смешивать нельзя.

## Частые ошибки

| Ошибка | Правильно |
| --- | --- |
| `= []` или `field(default=[])` | `field(default_factory=list)` |
| поле без умолчания после поля с умолчанием | порядок или `kw_only=True` |
| `self.x = ...` в `__post_init__` frozen-класса | `object.__setattr__(self, "x", ...)` |
| dataclass в set или ключом dict | `frozen=True` |
| наследник без `@dataclass` | декоратор на каждом классе с полями |

## dataclass и pydantic

| | dataclass | pydantic |
| --- | --- | --- |
| Установка | стандартная библиотека | `pip install pydantic` |
| Проверка и приведение типов | нет, вручную в `__post_init__` | да |
| Позиционные аргументы | да | нет |
| Атрибут без аннотации | атрибут класса | ошибка |
| `= []` по умолчанию | ошибка | можно |
| Копия с изменением | `replace(p, x=1)` | `p.model_copy(update={"x": 1})` |
| В dict | `asdict(p)` | `p.model_dump()` |
| JSON | `json.dumps(asdict(p), default=str)` | `p.model_dump_json()` |
