# Потоки и процессы: памятка

Python 3.11+. Каждый блок самостоятельный, запускается как скрипт.
Асинхронность (asyncio) - в [async.md](async.md).

**Содержание**

- [Что выбрать](#что-выбрать)
- [GIL в двух словах](#gil-в-двух-словах)
- [Потоки: ThreadPoolExecutor](#потоки-threadpoolexecutor)
- [Потоки: Thread и Lock](#потоки-thread-и-lock)
- [Потоки: очередь Queue](#потоки-очередь-queue)
- [Процессы: ProcessPoolExecutor](#процессы-processpoolexecutor)
- [Процессы: память не общая](#процессы-память-не-общая)
- [API concurrent.futures](#api-concurrentfutures)
- [Частые ошибки](#частые-ошибки)

## Что выбрать

| Задача | Чем | Почему |
|---|---|---|
| ждем сеть, диск, БД (I/O-bound) | потоки или asyncio | во время ожидания GIL отпущен, потоки работают параллельно |
| считаем на процессоре (CPU-bound) | процессы | у каждого процесса свой интерпретатор и свой GIL |
| много одновременных соединений (тысячи) | asyncio | поток на соединение - дорого по памяти |
| вызвать блокирующую функцию из async-кода | `asyncio.to_thread` | цикл событий не останавливается |

```python
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor


def cpu_task(n: int) -> int:
    return sum(i * i for i in range(n))


def io_task(seconds: float) -> float:
    time.sleep(seconds)                     # ожидание: GIL отпущен
    return seconds


def timed(executor_cls, func, args) -> float:
    start = time.perf_counter()
    with executor_cls(max_workers=4) as pool:
        list(pool.map(func, args))
    return round(time.perf_counter() - start, 2)


if __name__ == "__main__":
    print("I/O, 4 потока   :", timed(ThreadPoolExecutor, io_task, [0.5] * 4))         # ~0.5 с, а не 2
    print("CPU, 4 потока   :", timed(ThreadPoolExecutor, cpu_task, [3_000_000] * 4))  # как по очереди
    print("CPU, 4 процесса :", timed(ProcessPoolExecutor, cpu_task, [3_000_000] * 4)) # в разы быстрее
```

## GIL в двух словах

- GIL (Global Interpreter Lock) - блокировка в CPython: байткод Python в каждый момент выполняет
  только один поток процесса.
- GIL отпускается при блокирующем вводе-выводе (сокеты, файлы, `time.sleep`) и в C-коде, который
  сам его отпускает (`hashlib`, `zlib`, numpy). Поэтому потоки ускоряют ожидание и не ускоряют
  вычисления на чистом Python.
- GIL не делает код потокобезопасным: поток может переключиться между любыми байткод-инструкциями,
  `counter += 1` - это чтение, сложение и запись. Общие данные защищают `Lock`.
- Сборки без GIL (3.13t, 3.14t) существуют, но пока опциональны.

## Потоки: ThreadPoolExecutor

Основной инструмент: пул потоков сам их создает, раздает задачи и собирает результаты.

```python
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


def fetch(url: str) -> str:
    time.sleep(0.1)                         # имитация сетевого запроса
    if url.endswith("bad"):
        raise ConnectionError(url)
    return f"ok {url}"


urls = ["a", "b", "c/bad", "d"]

# map: результаты в порядке входа; исключение задачи вылетит при чтении ее результата
with ThreadPoolExecutor(max_workers=8) as pool:
    try:
        for result in pool.map(fetch, urls):
            print(result)
    except ConnectionError as e:
        print("ошибка:", e)

# submit + as_completed: результаты по мере готовности, ошибка - у конкретной задачи
with ThreadPoolExecutor(max_workers=8) as pool:
    futures = {pool.submit(fetch, url): url for url in urls}
    for future in as_completed(futures):
        url = futures[future]
        try:
            print(url, future.result())     # result() возвращает значение или бросает исключение задачи
        except ConnectionError as e:
            print(url, "ошибка:", e)
```

- Выход из `with` ждет завершения всех задач.
- Исключение в задаче не видно, пока не вызван `result()`: без него ошибка молча пропадает.

## Потоки: Thread и Lock

```python
import threading
import time

counter = 0
lock = threading.Lock()


def unsafe() -> None:
    global counter
    for _ in range(1000):
        value = counter
        time.sleep(0)                       # поток переключается между чтением и записью
        counter = value + 1


def safe() -> None:
    global counter
    for _ in range(1000):
        with lock:                          # чтение и запись - одна неделимая операция
            value = counter
            time.sleep(0)
            counter = value + 1


for target in (unsafe, safe):
    counter = 0
    threads = [threading.Thread(target=target) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()                            # дождаться завершения потока
    print(target.__name__, counter)         # unsafe - меньше 4000, safe - ровно 4000
```

| Примитив | Зачем |
|---|---|
| `Lock` | один поток в критической секции |
| `RLock` | тот же поток может захватить повторно (рекурсия) |
| `Semaphore(n)` | не больше n потоков одновременно, например n запросов к API |
| `Event` | один поток ждет `event.wait()`, другой разрешает `event.set()` |
| `threading.local()` | у каждого потока своя копия данных, например соединение с БД |
| `Thread(daemon=True)` | поток не держит программу: при выходе он просто обрывается |

## Потоки: очередь Queue

`queue.Queue` потокобезопасна: схема "производитель - потребители" без ручных блокировок.

```python
import queue
import threading

tasks: queue.Queue[int | None] = queue.Queue()
results: queue.Queue[int] = queue.Queue()


def worker() -> None:
    while True:
        item = tasks.get()                  # ждет, пока в очереди что-то появится
        if item is None:                    # сигнал остановки
            break
        results.put(item * item)


workers = [threading.Thread(target=worker) for _ in range(3)]
for w in workers:
    w.start()
for i in range(10):
    tasks.put(i)
for _ in workers:
    tasks.put(None)                         # по одному сигналу остановки на поток
for w in workers:
    w.join()
print(sorted(results.get() for _ in range(results.qsize())))
```

## Процессы: ProcessPoolExecutor

```python
import os
from concurrent.futures import ProcessPoolExecutor


def is_prime(n: int) -> bool:               # на верхнем уровне модуля, иначе процессу ее не передать
    if n < 2:
        return False
    return all(n % d for d in range(2, int(n**0.5) + 1))


if __name__ == "__main__":                  # обязательно: дочерний процесс может заново импортировать модуль
    numbers = range(1_000_000, 1_000_200)
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:
        flags = pool.map(is_prime, numbers, chunksize=50)
        primes = [n for n, ok in zip(numbers, flags) if ok]
    print(len(primes), primes[:3])
```

- Функция, аргументы и результат передаются между процессами через `pickle`. Нельзя передать
  `lambda`, вложенную функцию, соединение с БД, открытый файл.
- `chunksize` - отправлять задачи пачками: для мелких задач пересылка дороже самого вычисления.
- Запуск процесса дорогой (при `spawn` - десятки миллисекунд): процессы окупаются на тяжелых задачах.
- Способ запуска: `fork` (Linux до 3.14) копирует память родителя; `spawn` (macOS, Windows) и
  `forkserver` (Linux с 3.14) запускают Python заново и импортируют модуль - отсюда `__main__`.

## Процессы: память не общая

```python
from multiprocessing import Pool

counter = 0


def increment(_: int) -> int:
    global counter
    counter += 1                            # меняется копия в дочернем процессе
    return counter


if __name__ == "__main__":
    with Pool(2) as pool:
        print(pool.map(increment, range(4)))   # у каждого процесса свой счетчик
    print("в родителе:", counter)               # 0
```

| Как обменяться данными | Когда |
|---|---|
| вернуть результат из функции | почти всегда, проще всего |
| `multiprocessing.Queue`, `Pipe` | поток сообщений между процессами |
| `multiprocessing.Value`, `Array` | число или массив в общей памяти, с блокировкой |
| `multiprocessing.shared_memory` | большие массивы без копирования |
| `multiprocessing.Manager().dict()` | общий словарь через процесс-посредник, медленно |

## API concurrent.futures

Одинаковый для потоков и процессов: пул меняется одной строкой.

| Вызов | Что делает |
|---|---|
| `pool.submit(fn, *args)` | ставит задачу, сразу возвращает `Future` |
| `pool.map(fn, items, chunksize=...)` | результаты в порядке входа |
| `as_completed(futures, timeout=...)` | `Future` по мере готовности |
| `wait(futures, return_when=FIRST_COMPLETED)` | пара множеств `(done, not_done)` |
| `future.result(timeout=...)` | значение или исключение задачи |
| `future.exception()`, `cancel()`, `done()` | ошибка без выброса, отмена, готовность |
| `pool.shutdown(wait=True, cancel_futures=False)` | остановка пула, `with` делает это сам |

По умолчанию `max_workers`: у потоков `min(32, число ядер + 4)`, у процессов - число ядер.

## Частые ошибки

- Ждать ускорения вычислений от потоков: GIL выполняет байткод по одному потоку.
- Нет `if __name__ == "__main__":` - при `spawn` пул падает с `RuntimeError` или плодит процессы.
- `lambda` или вложенная функция в пуле процессов - ошибка `pickle`.
- Не вызвали `future.result()` - исключение задачи молча пропало.
- Общий счетчик или проверка "есть ли ключ, потом записать" без `Lock` - гонка, данные теряются.
- Два `Lock`, которые потоки берут в разном порядке, - взаимная блокировка (deadlock).
  Брать блокировки всегда в одном порядке.
- Глобальная переменная, измененная в дочернем процессе, в родителе не меняется.
- `fork` в процессе, где уже работают потоки, - блокировки копируются захваченными, дочерний
  процесс может зависнуть.
