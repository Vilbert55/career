# Итераторы, генераторы, декораторы: памятка

Оригинал (Claude Docs, можно выгрузить в PDF): https://claude.ai/code/artifact/3a2cb4d8-1622-4870-b12b-aecce3bb1f14

Python 3.10+.

## Итератор

Итерируемый объект (`list`, `str`, `dict`, файл) - у него есть `__iter__`, возвращает итератор.
Итератор - `__next__` отдает элемент или бросает `StopIteration`; `__iter__` возвращает self. Одноразовый.

```python
it = iter([1, 2, 3])
next(it)           # 1
next(it, None)     # значение по умолчанию вместо StopIteration


class Countdown:                        # итератор классом
    def __init__(self, start: int):
        self.current = start

    def __iter__(self):
        return self

    def __next__(self) -> int:
        if self.current <= 0:
            raise StopIteration
        value = self.current
        self.current -= 1
        return value


class Route:                            # контейнер: каждый for - новый проход
    def __init__(self, stops):
        self._stops = stops

    def __iter__(self):
        yield from self._stops
```

- `for x in obj`: `it = iter(obj)`, затем `next(it)` до `StopIteration`.
- `list()`, `sum()`, `in`, распаковка исчерпывают итератор.
- Проверка: `isinstance(x, collections.abc.Iterable)` / `Iterator`.

## Генератор

```python
def countdown(start: int):
    while start > 0:
        yield start                     # отдать значение и замереть до следующего next()
        start -= 1


g = countdown(3)                        # тело еще не выполнялось
list(g)                                 # [3, 2, 1]; второй list(g) - []

squares = (x * x for x in range(10))    # генераторное выражение
sum(x * x for x in range(10))           # 285


def flatten(items):
    for item in items:
        if isinstance(item, list):
            yield from flatten(item)    # отдать все элементы другого итерируемого
        else:
            yield item
```

- Нет `len()` и индексов: `list(g)` или `itertools.islice(g, 5)`.
- `return value` завершает генератор; значение - в `StopIteration.value` и в `x = yield from gen()`.

## Конвейер и пачки

```python
def read_lines(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield line.rstrip("\n")


def only_errors(lines):
    return (line for line in lines if "ERROR" in line)


def batched(items, size):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:                           # хвост
        yield batch


for batch in batched(only_errors(read_lines("app.log")), 100):
    ...
```

Проверку аргументов в генераторе выполнит только первый `next()`. Чтобы ошибка была сразу - обычная функция проверяет и возвращает внутренний генератор.

## itertools

| Функция | Что делает |
| --- | --- |
| `islice(it, 5)` | первые 5 элементов, в том числе бесконечного |
| `count(1)` | 1, 2, 3, ... |
| `cycle("AB")` | A, B, A, B, ... |
| `chain(a, b)` | все из a, потом из b |
| `groupby(sorted_items, key)` | группы соседних элементов - сначала сортировать по ключу |
| `batched(it, 100)` | пачки-кортежи, Python 3.12+ |
| `pairwise([1, 2, 3])` | (1, 2), (2, 3) |
| `accumulate([1, 2, 3])` | 1, 3, 6 |
| `product`, `permutations`, `combinations` | произведение, перестановки, сочетания |
| `tee(it, 2)` | два независимых итератора |

## contextmanager и send

```python
import time
from contextlib import contextmanager


@contextmanager
def timer(name):
    start = time.perf_counter()
    try:
        yield                           # тело with
    finally:                            # выполнится и при исключении
        print(f"{name}: {time.perf_counter() - start:.3f} с")


def running_avg():
    total, count, avg = 0, 0, None
    while True:
        value = yield avg               # send(x) кладет x сюда
        total += value
        count += 1
        avg = total / count


g = running_avg()
next(g)                                 # дойти до первого yield
g.send(10)                              # 10.0
g.send(20)                              # 15.0
```

## Декоратор

`@deco` над `def f` - то же, что `f = deco(f)`. Выполняется один раз при объявлении, обертка - на каждом вызове.

```python
import functools


def timed(func):
    @functools.wraps(func)                  # имя, docstring, __wrapped__
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)    # не забыть return
        finally:
            print(f"{func.__name__}: {time.perf_counter() - start:.3f} с")
    return wrapper


def make_counter():                         # замыкание
    count = 0

    def inc():
        nonlocal count                      # без nonlocal - UnboundLocalError
        count += 1
        return count

    return inc
```

Частые ошибки: нет `return` в обертке (всегда None); нет `wraps` (имя `wrapper`); `wrapper()` без `*args, **kwargs`.
Для `async def` обертка тоже `async def` и `return await func(...)`.

## Декоратор с параметрами

```python
def retry(times: int = 3, exceptions=(ConnectionError,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == times:
                        raise               # пробросить с исходным traceback
        return wrapper
    return decorator


@retry(times=5, exceptions=(TimeoutError,))     # @retry без скобок - ошибка
def fetch_tariff(zone): ...
```

- Порядок: `@a @b def f` = `a(b(f))`; при вызове сначала код `a`.
- Состояние - в замыкании (`cache = {}` внутри декоратора) или в классе с `__call__` + `functools.update_wrapper(self, func)`.
- Декоратор-класс на методе не получит `self`; для методов - декоратор-функция.

## Встроенные декораторы

| Декоратор | Что делает |
| --- | --- |
| `@functools.cache`, `@lru_cache(maxsize=128)` | кэш по хешируемым аргументам; `cache_clear()`, `cache_info()` |
| `@property`, `@x.setter` | метод как атрибут |
| `@functools.cached_property` | считается один раз на объект |
| `@staticmethod` | без `self` и `cls` |
| `@classmethod` | первый аргумент - класс; `from_dict(cls, d)` |
| `@abstractmethod` | обязателен к переопределению |
| `@contextmanager` | контекстный менеджер из генератора |

`lru_cache` на методе держит `self` в кэше - объекты не освобождаются.

## Коротко

| Что | Ответ |
| --- | --- |
| итерируемый vs итератор | у итератора еще `__next__` и состояние, он одноразовый |
| генератор vs список | ленивый, хранит только состояние, без `len` и индексов |
| `yield` vs `return` | `yield` ставит функцию на паузу, `return` завершает |
| `[f() for f in [lambda: i for i in range(3)]]` | `[2, 2, 2]` - позднее связывание; `lambda i=i: i` |
| декоратор класса | принимает и возвращает класс, как `@dataclass` |
