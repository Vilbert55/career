# Pydantic v2: памятка

02.10.2026. Оригинал (Claude Docs, можно выгрузить в PDF): https://claude.ai/code/artifact/4d0bac19-c231-4d3b-8d23-5ed0460252d5

Pydantic 2.x, Python 3.10+. Установка: `pip install pydantic`.

## 1. Модель и поля

Каждое поле - атрибут класса с аннотацией типа. Без аннотации pydantic падает с ошибкой при объявлении класса.

```python
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, Field


class Promo(BaseModel):
    code: str                                   # обязательное
    value: Decimal = Field(gt=0)                # обязательное, > 0
    max_discount: Decimal | None = None         # необязательное
    min_order: Decimal = Decimal("0")           # значение по умолчанию
    tags: list[str] = Field(default_factory=list)
    max_uses: int | None = Field(default=None, ge=1)

    CURRENCY: ClassVar[str] = "RUB"            # константа класса, не поле
```

| Как записать | Что значит |
| --- | --- |
| `x: int` | обязательное |
| `x: int \| None` | обязательное, но можно передать None |
| `x: int \| None = None` | необязательное |
| `x: int = Field(gt=0)` | обязательное с проверкой |
| `x: list[int] = []` | можно: pydantic копирует значение по умолчанию |
| `x: ClassVar[int] = 1` | атрибут класса, в валидации не участвует |

Ограничения `Field`: `gt`, `ge`, `lt`, `le` для чисел; `min_length`, `max_length`, `pattern` для строк и списков; `max_digits`, `decimal_places` для Decimal; `alias` - имя поля во входных данных; `description` - для документации.

## 2. Создание и ошибки валидации

Модель проверяет данные при создании и приводит типы: строка `"500.50"` станет `Decimal`, `"5"` станет `int`. При ошибке - `ValidationError` со списком всех проблем сразу.

```python
from pydantic import ValidationError

p = Promo(code="AUTUMN20", value="20")         # именованные аргументы, не позиционные
p = Promo.model_validate({"code": "A", "value": 5})          # из dict
p = Promo.model_validate_json('{"code": "A", "value": 5}')   # из JSON-строки

try:
    Promo(code="A", value=-1)
except ValidationError as e:
    print(e.error_count())         # 1
    print(e.errors()[0]["loc"])    # ('value',) - где
    print(e.errors()[0]["type"])   # 'greater_than' - что именно
```

- Позиционные аргументы `Promo("A", 5)` не работают: только по имени.
- Лишние поля во входных данных по умолчанию молча отбрасываются (см. `extra` в разделе 5).
- В тестах: `with pytest.raises(ValidationError):`.
- Без валидации, для данных, которым доверяем: `Promo.model_construct(...)`.

## 3. Валидаторы

`field_validator` проверяет или нормализует одно поле, `model_validator` - связку полей. Валидатор возвращает значение, а ошибку сообщает через `raise ValueError(...)`: pydantic завернет ее в `ValidationError`.

```python
from typing import Self

from pydantic import BaseModel, field_validator, model_validator


class Promo(BaseModel):
    code: str
    percent: Decimal | None = None
    fixed: Decimal | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("пустой код")
        return v

    @model_validator(mode="after")
    def one_kind_of_discount(self) -> Self:
        if (self.percent is None) == (self.fixed is None):
            raise ValueError("нужен ровно один вид скидки")
        return self
```

- `@classmethod` под `@field_validator` обязателен, `return` в конце - тоже. Забыл `return` - поле станет None.
- `mode="after"` (по умолчанию) - значение уже нужного типа. `mode="before"` - сырое значение до приведения типа.
- Один валидатор на несколько полей: `@field_validator("percent", "fixed")`.
- `model_validator(mode="after")` - метод экземпляра, принимает `self`, возвращает `self`.
- Простую нормализацию строк можно настроить без валидатора: `str_strip_whitespace`, `str_to_upper` в разделе 5.

## 4. Сериализация и копирование

| Вызов | Результат |
| --- | --- |
| `p.model_dump()` | dict, типы Python как есть (Decimal, datetime) |
| `p.model_dump(mode="json")` | dict только из JSON-типов (Decimal и datetime станут строками) |
| `p.model_dump_json()` | JSON-строка |
| `p.model_dump(exclude_none=True)` | без полей со значением None |
| `p.model_dump(include={"code"})` | только указанные поля; `exclude=` - наоборот |
| `p.model_dump(by_alias=True)` | ключи по alias |
| `p.model_copy(update={"value": 10})` | копия с изменениями, без повторной валидации |
| `p.model_copy(deep=True)` | глубокая копия |
| `Promo.model_fields` | описание полей класса |
| `Promo.model_json_schema()` | JSON Schema модели |

Изменения через `model_copy(update=...)` не проверяются. Если проверка нужна: `Promo.model_validate({**p.model_dump(), "value": 10})`.

Имена из pydantic v1 (`dict()`, `json()`, `parse_obj()`, `copy()`, `@validator`, `class Config`) в v2 устарели. Их часто встречают в старых ответах на Stack Overflow.

## 5. Настройки модели: ConfigDict

```python
from pydantic import BaseModel, ConfigDict


class Promo(BaseModel):
    model_config = ConfigDict(
        frozen=True,               # неизменяемая, хешируемая
        extra="forbid",            # лишние поля - ошибка
        str_strip_whitespace=True, # обрезать пробелы во всех str
    )

    code: str
```

| Настройка | Что делает |
| --- | --- |
| `frozen=True` | присваивание полю - ошибка; объект можно класть в set и делать ключом dict |
| `extra="forbid"` | лишние поля - ошибка; `"ignore"` - отбросить (по умолчанию); `"allow"` - сохранить |
| `validate_assignment=True` | проверять присваивание `p.value = ...` (без нее присваивание не проверяется) |
| `str_strip_whitespace=True` | обрезать пробелы по краям во всех строках |
| `str_to_upper=True` | перевести строки в верхний регистр |
| `strict=True` | без приведения типов: `"5"` для int - ошибка |
| `use_enum_values=True` | хранить в поле значение перечисления, а не сам член |
| `from_attributes=True` | создавать из объекта с атрибутами (ORM): `Promo.model_validate(row)` |
| `populate_by_name=True` | принимать и имя поля, и alias |

Наследник получает `model_config` родителя и может дополнить его своим.

## 6. Деньги, перечисления, даты

```python
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Kind(StrEnum):
    PERCENT = "percent"          # члены перечисления - заглавными буквами
    FIXED = "fixed"


class Promo(BaseModel):
    kind: Kind                   # примет Kind.PERCENT или строку "percent"
    value: Decimal = Field(gt=0, decimal_places=2)
    valid_until: datetime        # примет datetime или "2026-10-31T23:59:59"
    channel: Literal["app", "web"] = "app"   # фиксированный набор значений


KOPECK = Decimal("0.01")
discount = (Decimal("333.33") * Decimal("15") / 100).quantize(KOPECK, ROUND_DOWN)
```

- Деньги - только `Decimal`, не `float`: `0.1 + 0.2 != 0.3`. Создавать из строки: `Decimal("0.1")`, а не `Decimal(0.1)`.
- Округление до копеек: `x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`. Режим округления - вопрос к интервьюеру.
- Альтернатива Decimal - целые копейки в `int`.
- `StrEnum` (Python 3.11+) - член равен строке: `Kind.PERCENT == "percent"`. Для 3.10: `class Kind(str, Enum)`.
- Время в коде не брать через `datetime.now()` внутри логики: передавать `now` аргументом или функцию-часы в конструктор. Так срок действия легко тестировать.
- Не смешивать даты с часовым поясом и без: сравнение упадет с `TypeError`.

## 7. Наследование и несколько видов одной сущности

Общие поля - в базовом классе, различия - в наследниках. Абстрактные методы работают в модели напрямую: `BaseModel` уже умеет ABC. Поле-метка с `Literal` позволяет pydantic самому выбрать нужный класс из dict.

```python
from abc import ABC, abstractmethod
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class PromoBase(BaseModel, ABC):
    code: str
    min_order: Decimal = Decimal("0")

    @abstractmethod
    def discount(self, price: Decimal) -> Decimal: ...


class PercentPromo(PromoBase):
    kind: Literal["percent"] = "percent"
    percent: Decimal = Field(gt=0, le=100)
    max_discount: Decimal | None = None

    def discount(self, price: Decimal) -> Decimal:
        d = price * self.percent / 100
        return min(d, self.max_discount) if self.max_discount is not None else d


class FixedPromo(PromoBase):
    kind: Literal["fixed"] = "fixed"
    amount: Decimal = Field(gt=0)

    def discount(self, price: Decimal) -> Decimal:
        return min(self.amount, price)


AnyPromo = Annotated[PercentPromo | FixedPromo, Field(discriminator="kind")]

promo = TypeAdapter(AnyPromo).validate_python({"kind": "fixed", "code": "A", "amount": 100})
# -> FixedPromo


class Order(BaseModel):
    promo: AnyPromo | None = None   # так же работает поле внутри другой модели
```

- Методы модели - обычные методы класса: первый аргумент `self`.
- Константа класса без аннотации (`kind = "fixed"`) в модели - ошибка. Нужна аннотация: `Literal[...]`, если это поле-метка, или `ClassVar[...]`, если не поле.
- `TypeAdapter` валидирует любой тип, не только модель: `TypeAdapter(list[int]).validate_python(["1", 2])` вернет `[1, 2]`.

## 8. Типичные ошибки и выбор на собеседовании

| Ошибка | Как правильно |
| --- | --- |
| `kind = Kind.FIXED` без аннотации | `kind: Literal[...] = ...` или `kind: ClassVar[Kind] = ...` |
| `label: str = Field(...)` | просто `label: str` - поле и так обязательное |
| `label = str` | `label: str` - через двоеточие |
| `def calc():` в модели | `def calc(self):` |
| `x: int \| None` и ожидание, что поле необязательное | `x: int \| None = None` |
| деньги в `float` | `Decimal` или копейки в `int` |
| валидатор без `return` | вернуть значение (или `self` в `model_validator`) |
| `p.value = -5` и ожидание ошибки | `validate_assignment=True` или `frozen=True` |
| члены перечисления строчными (`percent = ...`) | `PERCENT = "percent"` |

**pydantic или dataclasses.** Pydantic нужен на границе системы: вход API, JSON, конфиги, данные извне. Для доменных объектов внутри логики часто хватает `dataclasses`. На секции Яндекса оценивают владение языком и стандартной библиотекой. Проще начать с dataclass, а pydantic брать, если в задаче есть сырой вход. Выбор стоит проговорить вслух.

```python
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Promo:
    code: str
    value: Decimal
    tags: list[str] = field(default_factory=list)   # тут [] нельзя

    def __post_init__(self):                       # проверки вручную
        if self.value <= 0:
            raise ValueError("value must be positive")
```

Разница: dataclass не проверяет и не приводит типы (`Promo(code=1, value="x")` создастся), принимает позиционные аргументы, работает без установки пакетов и быстрее создается.

Справка: [docs.pydantic.dev](https://docs.pydantic.dev/latest/concepts/models/), [dataclasses](https://docs.python.org/3/library/dataclasses.html).
