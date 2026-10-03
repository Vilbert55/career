# Итераторы, генераторы, декораторы: памятка

03.10.2026. Оригинал (Claude Docs, можно выгрузить в PDF): https://claude.ai/code/artifact/3a2cb4d8-1622-4870-b12b-aecce3bb1f14

Python 3.10+. Все примеры проверены запуском.

## 1. Итерируемый объект и итератор

**Итерируемый (iterable)** - по нему можно пройти `for`: у него есть `__iter__`, который возвращает итератор. Примеры: `list`, `str`, `dict`, `set`, файл, `range`.

**Итератор (iterator)** - объект с состоянием "где я сейчас". `__next__` отдает следующий элемент или бросает `StopIteration`, `__iter__` возвращает самого себя. Итератор одноразовый: прошел до конца - пуст.

```python
nums = [1, 2, 3]        # итерируемый, но не итератор
it = iter(nums)         # вызывает nums.__iter__()
next(it)                # 1   - вызывает it.__next__()
next(it)                # 2
next(it)                # 3
next(it)                # StopIteration
next(it, None)          # None - значение по умолчанию вместо исключения

# что делает for x in nums:
it = iter(nums)
while True:
    try:
        x = next(it)
    except StopIteration:
        break
    ...                 # тело цикла
```

Свой итератор классом:

```python
class Countdown:
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


list(Countdown(3))      # [3, 2, 1]
```

Итерируемый контейнер, который можно обойти много раз: `__iter__` каждый раз возвращает новый итератор. Проще всего - сделать `__iter__` генератором:

```python
class Route:
    def __init__(self, stops: list[str]):
        self._stops = stops

    def __iter__(self):
        yield from self._stops       # каждый вызов - новый генератор


r = Route(["A", "B"])
list(r), list(r)        # (['A', 'B'], ['A', 'B'])
c = Countdown(2)
list(c), list(c)        # ([2, 1], []) - итератор исчерпан
```

- Проверка на итерируемость: `isinstance(x, collections.abc.Iterable)`, на итератор: `isinstance(x, collections.abc.Iterator)`.
- `in`, `list()`, `sum()`, `max()`, `zip()`, распаковка `a, b = ...` - все работают через этот же протокол и исчерпывают итератор.

## 2. Генераторы

Функция с `yield` - генераторная функция. Ее вызов не выполняет тело, а возвращает генератор - итератор. Каждый `next()` выполняет тело до следующего `yield` и замирает, сохранив локальные переменные. Конец функции или `return` - `StopIteration`.

```python
def countdown(start: int):
    print("старт")
    while start > 0:
        yield start
        start -= 1


g = countdown(2)        # ничего не напечатало: тело еще не запускалось
next(g)                 # печатает "старт", возвращает 2
next(g)                 # 1
next(g)                 # StopIteration
```

Тот же `Countdown` из раздела 1 в три строки: генератор сам реализует `__iter__` и `__next__`.

**Генераторное выражение** - как list comprehension, но в круглых скобках и ленивое:

```python
squares_list = [x * x for x in range(10**6)]   # список целиком в памяти
squares_gen = (x * x for x in range(10**6))   # считает по одному по запросу
sum(x * x for x in range(10))                 # 285 - скобки функции можно не дублировать
```

**`yield from`** - отдать все элементы другого итерируемого:

```python
def flatten(items):
    for item in items:
        if isinstance(item, list):
            yield from flatten(item)     # рекурсия
        else:
            yield item


list(flatten([1, [2, [3, 4]], 5]))      # [1, 2, 3, 4, 5]
```

- Генератор одноразовый, как любой итератор. Второй проход - новый вызов функции.
- У генератора нет `len()` и индекса `g[0]`. Нужно - `list(g)` или `itertools.islice`.
- Память: генератор хранит только свое состояние, не все элементы. Поэтому им обрабатывают большие файлы и бесконечные потоки.
- `return value` в генераторе заканчивает его; значение попадает в `StopIteration.value` и в результат `x = yield from gen()`.

## 3. Генераторы на практике

**Конвейер:** каждая ступень принимает итерируемое и отдает генератор. В памяти одновременно одна строка, какого бы размера ни был файл.

```python
def read_lines(path):
    with open(path, encoding="utf-8") as f:
        for line in f:                      # файл сам итератор по строкам
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
    if batch:                               # хвост - частая ошибка на собеседовании
        yield batch


for batch in batched(only_errors(read_lines("app.log")), 100):
    send_to_alerting(batch)
```

**itertools** - что пригодится чаще всего:

| Функция | Что делает |
| --- | --- |
| `islice(it, 5)` | первые 5 элементов любого итератора, в том числе бесконечного |
| `count(1)` | 1, 2, 3, ... бесконечно |
| `cycle("AB")` | A, B, A, B, ... бесконечно (раунд-робин) |
| `chain(a, b)` | сначала все из a, потом из b |
| `groupby(sorted_items, key)` | группирует соседние элементы - сначала сортировать по тому же ключу |
| `batched(it, 100)` | пачки по 100, Python 3.12+ (в 3.10-3.11 - писать самому, как выше) |
| `pairwise([1, 2, 3])` | (1, 2), (2, 3), Python 3.10+ |
| `product`, `permutations`, `combinations` | декартово произведение, перестановки, сочетания |
| `accumulate([1, 2, 3])` | 1, 3, 6 - накопленные суммы |
| `tee(it, 2)` | два независимых итератора из одного |

**Генератор как контекстный менеджер:** код до `yield` - вход в `with`, после - выход. `finally` сработает и при исключении внутри `with`.

```python
import time
from contextlib import contextmanager


@contextmanager
def timer(name):
    start = time.perf_counter()
    try:
        yield                                 # сюда подставляется тело with
    finally:
        print(f"{name}: {time.perf_counter() - start:.3f} с")


with timer("расчет"):
    ...
```

**`send`** - передать значение внутрь генератора: оно станет результатом выражения `yield`. Спрашивают редко, но любят как вопрос "чем генератор отличается от корутины".

```python
def running_avg():
    total, count, avg = 0, 0, None
    while True:
        value = yield avg
        total += value
        count += 1
        avg = total / count


g = running_avg()
next(g)          # запустить до первого yield ("прайминг")
g.send(10)       # 10.0
g.send(20)       # 15.0
```

## 4. Декораторы: основа

Декоратор - функция, которая принимает функцию и возвращает другую (обертку). `@deco` над `def f` - это ровно `f = deco(f)` при объявлении функции. Работает, потому что функции в Python - обычные объекты, а вложенная функция помнит переменные внешней (замыкание).

```python
def make_counter():
    count = 0

    def inc():
        nonlocal count          # без nonlocal присваивание создаст локальную переменную
        count += 1
        return count

    return inc


c = make_counter()
c(), c()                        # (1, 2) - inc помнит count
```

Шаблон декоратора - выучить наизусть:

```python
import functools
import time


def timed(func):
    @functools.wraps(func)                  # сохранить имя, docstring, сигнатуру
    def wrapper(*args, **kwargs):           # принять любые аргументы
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)    # вызвать и вернуть результат
        finally:
            print(f"{func.__name__}: {time.perf_counter() - start:.3f} с")
    return wrapper


@timed
def calc_price(distance_km: float) -> float:
    """Стоимость поездки."""
    return 100 + 25 * distance_km


calc_price(4)               # печатает время, возвращает 200.0
calc_price.__name__         # 'calc_price' (без wraps было бы 'wrapper')
calc_price.__wrapped__      # исходная функция без декоратора
```

Три ошибки, которые ищут на собеседовании:

1. Забыл `return` в `wrapper` - декорированная функция всегда возвращает `None`.
2. Забыл `@functools.wraps` - пропадают `__name__` и `__doc__`, ломаются логи, отладка и фреймворки, которые смотрят на сигнатуру (FastAPI, pytest).
3. `wrapper()` без `*args, **kwargs` - декоратор работает только для функций без аргументов.

Декоратор выполняется один раз - при объявлении функции (обычно при импорте модуля). `wrapper` выполняется на каждом вызове.

Для async-функции обертка тоже `async def wrapper(...)` и `return await func(*args, **kwargs)`. Обычный `wrapper` вернет корутину, и замер времени покажет ноль.

## 5. Декораторы: параметры, порядок, классы, встроенные

**Декоратор с параметрами** - три уровня: функция параметров возвращает декоратор. `@retry(times=3)` = `f = retry(times=3)(f)`.

```python
import functools
import time


def retry(times: int = 3, delay: float = 0.1, exceptions=(ConnectionError,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, times + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if attempt == times:
                        raise                   # последняя попытка - пробросить ошибку
                    time.sleep(delay)
        return wrapper
    return decorator


@retry(times=5, exceptions=(TimeoutError,))
def fetch_tariff(zone: str) -> dict: ...
```

- `@retry` без скобок для такого декоратора - ошибка: функция попадет в `times`. Нужно `@retry()`.
- `raise` без аргумента пробрасывает текущее исключение с исходным traceback.

**Несколько декораторов** применяются снизу вверх, а выполняются сверху вниз:

```python
@a
@b
def f(): ...        # f = a(b(f)); при вызове: сначала код a, потом b, потом f
```

Пример: `@timed` над `@retry` замерит все попытки вместе, под `@retry` - каждую отдельно.

**Декоратор со состоянием.** Состояние живет в замыкании или в классе с `__call__`:

```python
def memoize(func):
    cache = {}                              # свой словарь у каждой декорированной функции

    @functools.wraps(func)
    def wrapper(*args):
        if args not in cache:
            cache[args] = func(*args)
        return cache[args]
    return wrapper


class CountCalls:
    def __init__(self, func):
        functools.update_wrapper(self, func)     # аналог wraps для класса
        self.func = func
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.func(*args, **kwargs)


@CountCalls
def ping(): ...
ping(); ping()
ping.calls          # 2
```

Декоратор-класс на методе не получит `self` без дополнительного `__get__`. Для методов проще декоратор-функция: `self` придет первым элементом `args`.

**Встроенные декораторы:**

| Декоратор | Зачем |
| --- | --- |
| `@functools.cache` / `@lru_cache(maxsize=128)` | мемоизация; аргументы должны быть хешируемыми; `f.cache_info()`, `f.cache_clear()` |
| `@property` | метод читается как атрибут; `@x.setter` - присваивание |
| `@functools.cached_property` | как property, но считается один раз на объект |
| `@staticmethod` | метод без `self` и `cls` |
| `@classmethod` | первый аргумент - класс; альтернативные конструкторы `from_dict(cls, d)` |
| `@abstractmethod` | метод, который обязан переопределить наследник |
| `@dataclass` | декоратор класса: генерирует `__init__`, `__repr__`, `__eq__` |
| `@contextmanager` | контекстный менеджер из генератора (раздел 3) |

`lru_cache` на методе держит ссылку на `self` в кэше, и объекты не удаляются из памяти. Это любимый вопрос "что тут не так".

## 6. Частые вопросы на собеседовании

| Вопрос | Короткий ответ |
| --- | --- |
| Чем итерируемый объект отличается от итератора? | У итерируемого есть `__iter__`, он выдает новый итератор. У итератора есть еще `__next__` и состояние, он одноразовый. |
| Как работает `for`? | `iter()` один раз, потом `next()` до `StopIteration`. |
| Чем генератор отличается от списка? | Ленивый: считает по одному элементу, хранит только состояние, одноразовый, без `len` и индексов. |
| Чем `yield` отличается от `return`? | `yield` отдает значение и ставит функцию на паузу с сохранением локальных переменных. `return` завершает функцию. |
| Что вернет вызов генераторной функции? | Объект-генератор. Тело не выполняется до первого `next()`. |
| Когда нужен генератор? | Большие данные и файлы, бесконечные последовательности, конвейеры, пагинация API. |
| Что такое декоратор? | Функция, которая принимает функцию и возвращает обертку. `@d` = `f = d(f)`. |
| Зачем `functools.wraps`? | Переносит на обертку `__name__`, `__doc__`, `__module__`, `__wrapped__` исходной функции. |
| Как сделать декоратор с параметрами? | Третий уровень вложенности: функция параметров возвращает декоратор. |
| В каком порядке работают несколько декораторов? | Применяются снизу вверх, при вызове внешний срабатывает первым. |
| Что такое замыкание? | Вложенная функция, которая использует переменные внешней и помнит их после выхода из нее. Для присваивания - `nonlocal`. |
| Что напечатает `[f() for f in [lambda: i for i in range(3)]]`? | `[2, 2, 2]`: лямбды читают `i` в момент вызова (позднее связывание). Исправление: `lambda i=i: i`. |
| Можно ли декорировать класс? | Да: декоратор принимает класс и возвращает класс, например `@dataclass`. |

Справка: [итераторы и генераторы](https://docs.python.org/3/howto/functional.html), [itertools](https://docs.python.org/3/library/itertools.html), [functools](https://docs.python.org/3/library/functools.html).
