# Декораторы: памятка

Python 3.11+. Каждый блок самостоятельный, можно копировать целиком.
`@deco` над `def f` - то же, что `f = deco(f)`: декоратор выполняется один раз при объявлении функции,
обертка - на каждом вызове.

## Шаблон

```python
import functools


def my_decorator(func):
    @functools.wraps(func)                      # сохранить имя, docstring, __wrapped__
    def wrapper(*args, **kwargs):
        # до вызова
        result = func(*args, **kwargs)
        # после вызова
        return result                           # без return функция всегда вернет None
    return wrapper


@my_decorator
def add(a, b):
    return a + b


add(2, 3)          # 5
add.__name__       # 'add' (без wraps было бы 'wrapper')
```

## functools.wraps

Без `wraps` декоратор работает, но обертка подменяет "паспорт" функции: в логах и трейсбеках имя `wrapper`,
`help()` без docstring, `inspect.signature` показывает `(*args, **kwargs)`. FastAPI и pytest читают сигнатуру,
чтобы подставить параметры и фикстуры, и без `wraps` ломаются. Ниже два одинаковых декоратора: с `wraps` и вручную.

```python
import functools
import inspect


def with_wraps(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def by_hand(func):                                  # то же самое без wraps
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    wrapper.__module__ = func.__module__
    wrapper.__name__ = func.__name__
    wrapper.__qualname__ = func.__qualname__
    wrapper.__doc__ = func.__doc__
    wrapper.__dict__.update(func.__dict__)
    wrapper.__wrapped__ = func                      # ссылка на оригинал: по ней inspect берет сигнатуру
    return wrapper


def bare(func):                                     # без копирования - для сравнения
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def add(a: int, b: int) -> int:
    """Сложить два числа."""
    return a + b


f1, f2, f3 = with_wraps(add), by_hand(add), bare(add)
f1.__name__, f2.__name__, f3.__name__               # ('add', 'add', 'wrapper')
f1.__doc__ == f2.__doc__ == add.__doc__             # True; у f3 - None
str(inspect.signature(f1)) == str(inspect.signature(f2)) == "(a: int, b: int) -> int"   # True
str(inspect.signature(f3))                          # '(*args, **kwargs)'
f1.__wrapped__ is f2.__wrapped__ is add             # True: оригинал без декоратора, удобно в тестах
```

`wraps` еще копирует аннотации и `__type_params__`, полный список - `functools.WRAPPER_ASSIGNMENTS`.
Для декоратора-класса то же делает `functools.update_wrapper(self, func)`.

## Таймер и лог вызовов

```python
import functools
import logging
import time

logger = logging.getLogger(__name__)


def timed(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:                                # выполнится и при исключении
            logger.info("%s: %.3f с", func.__name__, time.perf_counter() - start)
    return wrapper


def log_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info("вызов %s args=%r kwargs=%r", func.__name__, args, kwargs)
        try:
            result = func(*args, **kwargs)
        except Exception:
            logger.exception("ошибка в %s", func.__name__)
            raise                               # пробросить дальше
        logger.info("%s вернула %r", func.__name__, result)
        return result
    return wrapper
```

## С параметрами: retry

```python
import functools
import time


def retry(times: int = 3, exceptions: tuple[type[Exception], ...] = (ConnectionError,), delay: float = 0):
    def decorator(func):                        # три уровня: параметры -> функция -> обертка
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == times:
                        raise                   # последняя попытка - пробросить исходную ошибку
                    time.sleep(delay)
        return wrapper
    return decorator


@retry(times=5, exceptions=(TimeoutError,))     # со скобками, даже без аргументов: @retry()
def fetch_tariff(zone: str) -> int:
    return 100
```

## Можно и со скобками, и без

```python
import functools


def trace(func=None, *, prefix: str = ">>"):
    if func is None:                            # вызвали как @trace(prefix=...)
        return functools.partial(trace, prefix=prefix)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(prefix, func.__name__)
        return func(*args, **kwargs)
    return wrapper


@trace
def a(): ...


@trace(prefix="--")
def b(): ...
```

## Состояние: счетчик, кэш, ограничение вызовов

```python
import functools


def count_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        wrapper.calls += 1                      # состояние - атрибут обертки
        return func(*args, **kwargs)
    wrapper.calls = 0
    return wrapper


def memoize(func):
    cache = {}                                  # состояние - в замыкании

    @functools.wraps(func)
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]

    wrapper.cache_clear = cache.clear
    return wrapper


def once(func):
    called = False
    result = None

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal called, result                 # без nonlocal присваивание создаст локальную переменную
        if not called:
            result = func(*args, **kwargs)
            called = True
        return result
    return wrapper


@count_calls
def ping(): ...


ping(); ping()
ping.calls         # 2
```

## Декоратор-класс

```python
import functools


class CountCalls:
    def __init__(self, func):
        functools.update_wrapper(self, func)    # аналог wraps для класса
        self.func = func
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.func(*args, **kwargs)


@CountCalls
def ping(): ...
```

На методе класса такой декоратор не получит `self`. Для методов - декоратор-функция: `self` придет в `args[0]`.

## Для async-функций

```python
import asyncio
import functools
import time


def async_timed(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):         # обертка тоже async
        start = time.perf_counter()
        try:
            return await func(*args, **kwargs)  # и await внутри
        finally:
            print(f"{func.__name__}: {time.perf_counter() - start:.3f} с")
    return wrapper


@async_timed
async def load():
    await asyncio.sleep(0.1)
    return 42


asyncio.run(load())    # 42
```

## Регистрация: декоратор возвращает функцию без обертки

```python
HANDLERS = {}


def handler(event: str):
    def decorator(func):
        HANDLERS[event] = func
        return func                             # функцию не меняем, только запоминаем
    return decorator


@handler("order_created")
def on_order_created(data): ...


HANDLERS["order_created"](data={})             # вызов по имени события
```

Так устроены `@app.get("/path")` во FastAPI и `@pytest.fixture`.

## Декоратор класса

```python
def add_repr(cls):
    def __repr__(self):
        fields = ", ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{cls.__name__}({fields})"
    cls.__repr__ = __repr__
    return cls                                  # принимает и возвращает класс, как @dataclass


@add_repr
class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y


Point(1, 2)        # Point(x=1, y=2)
```

## Встроенные декораторы

```python
import functools
from abc import ABC, abstractmethod


class Order(ABC):
    def __init__(self, items: list[int]):
        self._items = items

    @property                                   # метод как атрибут: order.total
    def total(self) -> int:
        return sum(self._items)

    @property
    def items(self) -> list[int]:
        return self._items

    @items.setter                               # order.items = [...]
    def items(self, value: list[int]) -> None:
        if not value:
            raise ValueError("пустой заказ")
        self._items = value

    @functools.cached_property                  # считается один раз на объект
    def report(self) -> str:
        return f"{len(self._items)} позиций"

    @classmethod                                # альтернативный конструктор
    def from_csv(cls, line: str):
        return cls([int(x) for x in line.split(",")])

    @staticmethod                               # без self и cls
    def is_valid_price(price: int) -> bool:
        return price > 0

    @abstractmethod                             # наследник обязан переопределить
    def deliver(self) -> None: ...


@functools.cache                                # кэш без ограничения размера
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


@functools.lru_cache(maxsize=128)               # кэш на 128 последних наборов аргументов
def tariff(zone: str) -> int:
    return 100


fib(50)            # 12586269025
fib.cache_info()   # hits, misses, maxsize, currsize; fib.cache_clear() - сбросить
```

## Порядок и замыкания

```python
def a(func):
    def wrapper():
        return "a(" + func() + ")"
    return wrapper


def b(func):
    def wrapper():
        return "b(" + func() + ")"
    return wrapper


@a                 # f = a(b(f)): применяется снизу вверх
@b
def f():
    return "f"


f()                # 'a(b(f))': при вызове первым срабатывает внешний

funcs = [lambda: i for i in range(3)]
[g() for g in funcs]          # [2, 2, 2]: замыкание видит последнее значение i
funcs = [lambda i=i: i for i in range(3)]
[g() for g in funcs]          # [0, 1, 2]: значение зафиксировано в аргументе по умолчанию
```

## Частые ошибки

| Ошибка | Правильно |
| --- | --- |
| нет `return` в обертке | `return func(*args, **kwargs)` |
| нет `@functools.wraps(func)` | имя и docstring станут от `wrapper` |
| `def wrapper():` без аргументов | `def wrapper(*args, **kwargs):` |
| `@retry` без скобок у декоратора с параметрами | `@retry()` или вариант "со скобками и без" |
| `return wrapper()` в декораторе | `return wrapper` - вернуть функцию, не вызывать |
| синхронная обертка на `async def` | `async def wrapper` и `return await func(...)` |
| `lru_cache` на методе | держит `self` в кэше; кэшировать функцию или `cached_property` |
