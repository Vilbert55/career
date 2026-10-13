# SQL: основы и ловушки

Примеры проверены на PostgreSQL 14. Физическое выполнение соединений, индексы, блокировки и отличия Greenplum -
в [greenplum.md](greenplum.md).

**Содержание**

- [Порядок выполнения запроса](#порядок-выполнения-запроса)
- [NULL](#null)
- [Соединения](#соединения)
- [Группировка и агрегаты](#группировка-и-агрегаты)
- [Оконные функции](#оконные-функции)
- [Подзапросы и CTE](#подзапросы-и-cte)
- [Транзакции и изоляция](#транзакции-и-изоляция)
- [Типы данных](#типы-данных)
- [Мелочи, на которых ловят](#мелочи-на-которых-ловят)
- [Типовые задачи: приемы](#типовые-задачи-приемы)

## Порядок выполнения запроса

```
FROM, JOIN -> WHERE -> GROUP BY -> HAVING -> оконные функции -> SELECT -> DISTINCT -> ORDER BY -> LIMIT
```

- Псевдоним из `SELECT` в `WHERE` и `HAVING` не виден: `column "dbl" does not exist`. В `ORDER BY` виден,
  в `GROUP BY` Postgres тоже разрешает.
- `WHERE` фильтрует строки до группировки, `HAVING` - группы после нее. Условие без агрегата пишут в `WHERE`:
  меньше строк попадет в группировку.
- Оконные функции считаются после `HAVING`, поэтому в `WHERE` их нельзя: `window functions are not allowed in WHERE`.
  Фильтр по окну - через подзапрос или CTE.
- Без `ORDER BY` порядок строк не гарантирован, даже если "всегда так выходило". `LIMIT` без `ORDER BY` - любые строки.

## NULL

`NULL` - "значение неизвестно". Логика трехзначная: `TRUE`, `FALSE`, `NULL`. `WHERE` оставляет только `TRUE`.

| Выражение | Результат |
|---|---|
| `NULL = NULL`, `NULL <> 1` | `NULL` |
| `NULL IS NULL` | `true` |
| `NULL IS DISTINCT FROM NULL` | `false` - сравнение, где `NULL` равен `NULL` |
| `'a' \|\| NULL` | `NULL`; `concat('a', NULL)` дает `'a'` |
| `2 IN (1, NULL)` | `NULL` |
| `2 NOT IN (1, NULL)` | `NULL` - поэтому `NOT IN` с `NULL` в подзапросе возвращает пусто |

Агрегаты на `(1), (NULL), (3)`:

| `COUNT(*)` | `COUNT(x)` | `SUM(x)` | `AVG(x)` |
|---|---|---|---|
| 3 | 2 | 4 | 2 - среднее по двум, `NULL` не считается |

- `SUM` пустого набора - `NULL`, не 0: `COALESCE(SUM(x), 0)`.
- `WHERE x <> 5` теряет строки с `NULL` в `x`. Нужны они - `WHERE x IS DISTINCT FROM 5`.
- `GROUP BY` и `DISTINCT` собирают все `NULL` в одну группу. `UNIQUE` допускает много `NULL`.
- В Postgres `NULL` больше любого значения: `ORDER BY x DESC LIMIT 1` вернет `NULL`, если он есть.
  Лечится `ORDER BY x DESC NULLS LAST`.
- В соединении `NULL` не равен ничему: строка с `NULL` в ключе не находит пары.

## Соединения

| Вид | Что вернет |
|---|---|
| `JOIN` = `INNER JOIN` | только пары с совпадением |
| `LEFT JOIN` = `LEFT OUTER JOIN` | все строки левой; справа `NULL`, если пары нет |
| `RIGHT JOIN` | все строки правой; на практике пишут `LEFT`, поменяв таблицы местами |
| `FULL JOIN` | все строки обеих сторон |
| `CROSS JOIN` | все пары, n × m |

Ловушка 1: условие на правую таблицу в `WHERE` превращает `LEFT JOIN` в `INNER`. Строки без пары
имеют справа `NULL`, а `NULL > 200000` - не `TRUE`.

```sql
-- отдел без подходящих сотрудников пропадет
SELECT d.name, e.name FROM departments d LEFT JOIN employees e ON e.dept_id = d.id WHERE e.salary > 200000;
-- все отделы останутся
SELECT d.name, e.name FROM departments d LEFT JOIN employees e ON e.dept_id = d.id AND e.salary > 200000;
```

Ловушка 2: соединение один-ко-многим размножает строки, и агрегат по "одной" стороне раздувается.

```sql
-- сумма заказа повторится столько раз, сколько у него платежей
SELECT SUM(o.amount) FROM orders o JOIN payments p ON p.order_id = o.id;
-- сначала свернуть "многие", потом соединять
SELECT SUM(o.amount), SUM(p.paid)
FROM orders o
LEFT JOIN (SELECT order_id, SUM(amount) AS paid FROM payments GROUP BY order_id) p ON p.order_id = o.id;
```

Антисоединение - строки без пары - пишут тремя способами:

```sql
SELECT * FROM departments d WHERE NOT EXISTS (SELECT 1 FROM employees e WHERE e.dept_id = d.id);  -- лучший
SELECT d.* FROM departments d LEFT JOIN employees e ON e.dept_id = d.id WHERE e.id IS NULL;        -- тоже верно
SELECT * FROM departments WHERE id NOT IN (SELECT dept_id FROM employees);                          -- пусто, если есть dept_id IS NULL
```

- Соединение таблицы с самой собой: `employees e JOIN employees m ON m.id = e.manager_id`.
- `USING (id)` - короткая запись равенства одноименных колонок. `NATURAL JOIN` соединяет по всем одноименным
  колонкам и ломается от новой колонки в таблице - не использовать.

## Группировка и агрегаты

- Каждая колонка в `SELECT` либо в `GROUP BY`, либо внутри агрегата. Postgres прощает колонки, которые зависят
  от первичного ключа из `GROUP BY`.
- Условный агрегат: `COUNT(*) FILTER (WHERE status = 'paid')` или `SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END)`.
- `COUNT(DISTINCT client_id)` - число разных значений, `NULL` не считается.
- `string_agg(name, ', ' ORDER BY name)`, `array_agg(x)` - собрать значения группы в строку или массив.
- `GROUP BY ROLLUP (year, month)` - итоги по месяцам, по годам и общий в одном запросе.

## Оконные функции

Окно считает значение по набору строк, не схлопывая их: каждая строка остается в результате.

```sql
функция() OVER (PARTITION BY группа ORDER BY порядок ROWS BETWEEN начало AND конец)
```

| Функция | Что дает |
|---|---|
| `ROW_NUMBER()` | 1, 2, 3, ... без повторов; у равных порядок произвольный |
| `RANK()` | равным - одно место, следующее с пропуском: 1, 1, 3 |
| `DENSE_RANK()` | равным - одно место, без пропуска: 1, 1, 2 |
| `LAG(x, n, по_умолчанию)`, `LEAD(...)` | значение из строки на n раньше или позже |
| `FIRST_VALUE(x)`, `LAST_VALUE(x)`, `NTH_VALUE(x, n)` | значение из первой, последней, n-й строки рамки |
| `NTILE(n)` | номер корзины при делении на n равных частей |
| `SUM`, `AVG`, `COUNT`, `MIN`, `MAX` с `OVER` | агрегат по окну: нарастающий итог, доля от целого |

На зарплатах `300, 300, 250, 250, 180`, окно `ORDER BY s DESC`:

| s | ROW_NUMBER | RANK | DENSE_RANK | SUM, рамка по умолчанию | SUM, `ROWS` |
|---|---|---|---|---|---|
| 300 | 1 | 1 | 1 | 600 | 300 |
| 300 | 2 | 1 | 1 | 600 | 600 |
| 250 | 3 | 3 | 2 | 1100 | 850 |
| 250 | 4 | 3 | 2 | 1100 | 1100 |
| 180 | 5 | 5 | 3 | 1280 | 1280 |

- **Рамка по умолчанию.** С `ORDER BY` это `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW`: в рамку входят
  все строки с тем же значением `ORDER BY`. Поэтому нарастающий итог "прыгает" на равных значениях. Построчный
  итог - `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` или уникальный `ORDER BY`. Без `ORDER BY` рамка -
  весь раздел.
- **`LAST_VALUE` с рамкой по умолчанию** возвращает текущую строку (рамка кончается на ней). Нужна рамка
  до конца раздела: `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`, или `FIRST_VALUE` с обратным порядком.
- Окно поверх агрегата: `SUM(SUM(amount)) OVER ()` - доля группы в общем итоге в одном запросе.
- Одно окно на несколько функций: `... OVER w ... WINDOW w AS (PARTITION BY dept_id ORDER BY salary DESC)`.
- Скользящее среднее за 7 строк: `AVG(x) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)`.

## Подзапросы и CTE

- **Скалярный подзапрос** в `SELECT` или в сравнении должен вернуть не больше одной строки, иначе
  `more than one row returned by a subquery used as an expression`. Ни одной строки - `NULL`.
- **`IN` и `EXISTS`** Postgres обычно выполняет одинаково (полусоединение). Разница только у отрицаний:
  `NOT IN` ломается на `NULL`, `NOT EXISTS` - нет.
- **Коррелированный подзапрос** ссылается на внешнюю строку. Если оптимизатор не превратит его в соединение,
  он выполнится для каждой строки.
- **CTE** (`WITH`) - для читаемости. С Postgres 12 CTE встраивается в запрос, как подзапрос. Раньше он всегда
  считался отдельно и мешал оптимизатору. Управление: `WITH x AS MATERIALIZED (...)`, `AS NOT MATERIALIZED`.
- **Рекурсивный CTE** - иерархии и графы:

```sql
WITH RECURSIVE chain AS (
    SELECT id, name, manager_id, 1 AS level FROM employees WHERE manager_id IS NULL   -- якорь: корень
    UNION ALL
    SELECT e.id, e.name, e.manager_id, c.level + 1
    FROM employees e JOIN chain c ON e.manager_id = c.id                              -- шаг: подчиненные
)
SELECT * FROM chain ORDER BY level, id;
```

- **`LATERAL`** - подзапрос видит колонки таблицы слева. Топ-N на группу с индексом:
  `FROM departments d CROSS JOIN LATERAL (SELECT ... FROM employees e WHERE e.dept_id = d.id ORDER BY salary DESC LIMIT 3) t`.

## Транзакции и изоляция

### Транзакция

Транзакция - несколько команд, которые выполняются целиком или не выполняются совсем. Пример - перевод денег:

```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;      -- оба изменения сохранены; ROLLBACK или сбой посередине - ни одного
```

Четыре свойства транзакции - ACID:
- **A**tomicity, атомарность - все или ничего;
- **C**onsistency, согласованность - ограничения (`CHECK`, `UNIQUE`, внешние ключи) соблюдены;
- **I**solation, изоляция - параллельные транзакции мешают друг другу только в пределах уровня изоляции;
- **D**urability, долговечность - после `COMMIT` данные переживут сбой: они уже в журнале (WAL).

### Как Postgres изолирует транзакции

Каждая транзакция читает базу как фотографию - **снимок** на какой-то момент. Чужие изменения, сделанные после
снимка, она не видит. `UPDATE` не перезаписывает строку: он создает ее новую версию, а старая остается для тех,
у кого снимок более ранний. Поэтому чтение никого не ждет. Старые версии потом убирает `VACUUM`. Это называется MVCC.

Уровень изоляции решает, когда делается снимок:

| Уровень | Когда снимок | Простыми словами |
|---|---|---|
| **Read Committed** - по умолчанию | перед каждой командой | каждая команда видит все, что другие успели зафиксировать |
| **Repeatable Read** | один раз, перед первой командой транзакции | вся транзакция видит базу как на момент своего начала |
| **Serializable** | как в Repeatable Read | плюс Postgres следит, чтобы итог был как при выполнении транзакций по очереди; если нет - одна из них падает |

Read Uncommitted в Postgres работает как Read Committed: чужие незафиксированные данные (грязное чтение)
не видны никогда. Уровень задают так: `BEGIN ISOLATION LEVEL REPEATABLE READ;`.

### Что может пойти не так

**1. Неповторяемое чтение.** Данные меняются посреди транзакции.

| Сессия A | Сессия B |
|---|---|
| `BEGIN;` `SELECT balance` - 100 | |
| | `UPDATE ... SET balance = 150; COMMIT;` |
| `SELECT balance` - 150 | |

В Read Committed второй `SELECT` видит 150. В Repeatable Read - снова 100. Фантом - то же самое для набора строк:
повторный `SELECT COUNT(*) ... WHERE ...` вернул другое число.

**2. Потерянное обновление.** Приложение прочитало значение, посчитало новое у себя и записало.

| Сессия A: пополнение на 50 | Сессия B: списание 30 |
|---|---|
| `SELECT balance` - 100 | |
| | `SELECT balance` - 100 |
| `UPDATE ... SET balance = 150; COMMIT;` | |
| | `UPDATE ... SET balance = 70; COMMIT;` |

Итог 70, правильно 120: пополнение потеряно. Как защититься:
- считать в самом запросе: `SET balance = balance - 30`. `UPDATE` берет последнее зафиксированное значение,
  а если строку держит чужая транзакция - сначала ждет ее;
- обе сессии читают через `SELECT ... FOR UPDATE`: B ждет уже на чтении и прочитает 150;
- Repeatable Read: `UPDATE` у B упадет с `could not serialize access due to concurrent update`, приложение
  повторит транзакцию.

**3. Write skew - аномалия сериализации.** Две транзакции меняют разные строки, но вместе нарушают общее правило.
Правило: на дежурстве хотя бы один врач. Сейчас дежурят двое.

| Сессия A | Сессия B |
|---|---|
| `SELECT COUNT(*)` дежурных - 2, можно уйти | `SELECT COUNT(*)` дежурных - 2, можно уйти |
| `UPDATE` - врач A уходит; `COMMIT;` | `UPDATE` - врач B уходит; `COMMIT;` |

Итог - никого. Строки разные, поэтому друг друга они не ждут, и Repeatable Read не помогает. Спасает только
Serializable: вторая транзакция падает с `could not serialize access due to read/write dependencies among transactions`.

### Итог

| Уровень | Неповторяемое чтение, фантом | Потерянное обновление | Write skew |
|---|---|---|---|
| Read Committed | бывает | бывает | бывает |
| Repeatable Read | защищает | защищает - ошибкой | бывает |
| Serializable | защищает | защищает - ошибкой | защищает - ошибкой |

- Ошибка сериализации на Repeatable Read и Serializable - штатная ситуация: приложение повторяет транзакцию целиком.
- На практике обычно Read Committed плюс `UPDATE ... SET x = x - 30` или `SELECT ... FOR UPDATE`. Serializable -
  когда правило охватывает несколько строк и ошибка недопустима.
- Greenplum 6: по умолчанию тоже Read Committed; `SERIALIZABLE` молча становится `REPEATABLE READ`.

## Типы данных

| Задача | Тип | Почему |
|---|---|---|
| деньги | `numeric(15, 2)` или копейки в `bigint` | точная арифметика |
| дробные измерения | `double precision` | быстро, но неточно: `0.1 + 0.2 = 0.30000000000000004` |
| момент времени | `timestamptz` | хранит момент в UTC, показывает в часовом поясе сессии |
| время "по часам" без пояса | `timestamp` | расписание "в 9:00 по местному" |
| строки | `text` или `varchar(n)` | по скорости одинаковы, `varchar(n)` - только ограничение длины |
| идентификатор | `bigint GENERATED ALWAYS AS IDENTITY` или `uuid` | `serial` - старый способ |

- Тип `money` в Postgres есть, но его не используют. Формат зависит от `lc_monetary` сервера:
  `1234.567::money` выводится как `$1,234.57`. Валюта одна, дробная часть фиксирована, а при переносе на сервер
  с другой локалью значения меняют смысл.

## Мелочи, на которых ловят

- `5 / 2 = 2`: целые делятся нацело. `5 / 2.0 = 2.5`, `5 % 2 = 1`.
- `UNION` убирает дубли (сортирует или хеширует), `UNION ALL` - нет и дешевле. `INTERSECT` - пересечение,
  `EXCEPT` - разность.
- Диапазон дат - полуинтервал: `created_at >= DATE '2026-10-01' AND created_at < DATE '2026-11-01'`.
  `BETWEEN '2026-10-01' AND '2026-10-31'` на `timestamp` теряет весь последний день после полуночи.
- `DELETE` - строки по условию, с триггерами, место освобождает `VACUUM`. `TRUNCATE` - вся таблица сразу,
  берет `AccessExclusiveLock`. `DROP` - удаляет саму таблицу. В Postgres все три откатываются в транзакции.
- `COUNT(*)` и `COUNT(1)` одинаковы.
- `LIKE 'abc%'` может использовать B-tree (при локали, отличной от `C`, нужен индекс с `text_pattern_ops`),
  `LIKE '%abc'` - нет.
- Вставка или обновление: `INSERT ... ON CONFLICT (id) DO UPDATE SET amount = EXCLUDED.amount` (Postgres 9.5+).
  В Greenplum 6 `ON CONFLICT` нет: синтаксическая ошибка.
- Нормальные формы: 1НФ - в ячейке одно значение; 2НФ - неключевые колонки зависят от всего составного ключа;
  3НФ - неключевые колонки не зависят друг от друга. В хранилищах денормализуют ради скорости чтения.

## Типовые задачи: приемы

| Задача | Прием |
|---|---|
| N-я по величине зарплата | `DENSE_RANK() OVER (ORDER BY salary DESC) = N`; `ORDER BY ... OFFSET N-1` ломается на равных |
| топ-N в каждой группе | `ROW_NUMBER`/`RANK`/`DENSE_RANK() OVER (PARTITION BY ...)` в подзапросе; Postgres: `DISTINCT ON` для топ-1 |
| найти дубли | `GROUP BY` по колонкам дубля `HAVING COUNT(*) > 1` |
| удалить дубли, оставить один | `ROW_NUMBER() OVER (PARTITION BY колонки ORDER BY id)` и удалить строки с номером больше 1 |
| нарастающий итог | `SUM(x) OVER (PARTITION BY ... ORDER BY ... ROWS UNBOUNDED PRECEDING)` |
| сравнить с предыдущей строкой | `LAG(x) OVER (PARTITION BY ... ORDER BY ...)` |
| больше, чем у руководителя | соединение таблицы с собой по `manager_id` |
| группа без записей | `NOT EXISTS` |
| непрерывные периоды (gaps and islands) | `дата - ROW_NUMBER() OVER (ORDER BY дата)` одинакова внутри серии подряд идущих дат |
