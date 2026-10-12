# Greenplum и PostgreSQL: памятка

Greenplum 6 построен на PostgreSQL 9.4, Greenplum 7 - на PostgreSQL 12. В 2024 году Broadcom закрыл исходники
Greenplum; в России работают Arenadata DB (ADB) и открытый форк Greengage DB. Примеры и планы сняты
на Greenplum 6.21.3 с 16 сегментами, примеры для Postgres - на PostgreSQL 14.

**Содержание**

- [Главное отличие: MPP](#главное-отличие-mpp)
- [Распределение данных](#распределение-данных)
- [Motion и чтение плана](#motion-и-чтение-плана)
- [EXPLAIN ANALYZE: факт по сегментам](#explain-analyze-факт-по-сегментам)
- [Оптимизаторы: ORCA и планировщик Postgres](#оптимизаторы-orca-и-планировщик-postgres)
- [Хранение: heap, AO, AOCS](#хранение-heap-ao-aocs)
- [Партиционирование](#партиционирование)
- [Индексы](#индексы)
- [Память, ресурсы, конкуренция](#память-ресурсы-конкуренция)
- [Блокировки](#блокировки)
- [Сводная таблица отличий](#сводная-таблица-отличий)
- [Почему запрос медленный: чек-лист](#почему-запрос-медленный-чек-лист)

## Главное отличие: MPP

- **Мастер (координатор)** принимает запрос, строит план, раздает его сегментам и собирает результат.
  Хранит системный каталог, строк пользовательских таблиц у него нет. Есть резервный мастер (standby).
- **Сегменты** - отдельные экземпляры Postgres, у каждого своя часть строк каждой таблицы. Работают
  параллельно, по принципу shared nothing: у каждого свой диск, память и процессы. У каждого primary-сегмента
  есть mirror на другом хосте.
- **Interconnect** - сеть, по которой сегменты пересылают друг другу строки во время запроса.
- Запрос выполняется со скоростью самого медленного сегмента. Отсюда главные темы: равномерное распределение
  данных и как можно меньше пересылок между сегментами.
- Масштабирование горизонтальное: добавить хосты и сегменты (`gpexpand`), затем перераспределить таблицы.

## Распределение данных

```sql
CREATE TABLE orders (id bigint, customer_id bigint, amount numeric)
DISTRIBUTED BY (customer_id);          -- строка уходит на сегмент по хешу ключа

CREATE TABLE currency (code text, name text)
DISTRIBUTED REPLICATED;                -- полная копия на каждом сегменте (с GP6): маленькие справочники

CREATE TABLE raw_events (payload text)
DISTRIBUTED RANDOMLY;                  -- по кругу: равномерно, но соединения всегда с пересылкой
```

- Без `DISTRIBUTED` Greenplum 6 берет первичный ключ или первую колонку подходящего типа - часто неудачно.
- **Как выбрать ключ:** много разных значений и равномерное распределение; мало `NULL` (все `NULL` попадут
  на один сегмент); колонка, по которой соединяются большие таблицы, - тогда соединение идет локально, без пересылки.
- **Перекос (skew)** - на одном сегменте строк сильно больше, чем на других. Проверка:

```sql
SELECT gp_segment_id, count(*) FROM orders GROUP BY 1 ORDER BY 2 DESC;
SELECT * FROM gp_toolkit.gp_skew_coefficients;   -- коэффициент перекоса по всем таблицам базы
```

- `gp_skew_coefficients` пересчитывает строки каждой таблицы базы, на большой базе это долго. Для одной таблицы
  хватает запроса по `gp_segment_id`.

- Перекос бывает и при обработке: данные распределены ровно, но соединение или группировка идут по колонке
  с частым значением.
- Сменить ключ: `ALTER TABLE orders SET DISTRIBUTED BY (id);` - таблица переписывается целиком.
- `PRIMARY KEY` и `UNIQUE` должны включать все колонки ключа распределения: уникальность проверяется
  на каждом сегменте отдельно. Внешние ключи объявить можно, но Greenplum их не проверяет.

## Motion и чтение плана

Motion - шаг плана, на котором строки пересылаются между сегментами. Это самое дорогое в плане.

| Motion | Что делает | Когда |
|---|---|---|
| `Gather Motion N:1` | собирает строки с сегментов на мастер | итог запроса |
| `Redistribute Motion N:N` | пересылает строки по хешу нового ключа | соединение или группировка не по ключу распределения |
| `Broadcast Motion N:N` | отправляет всю таблицу на каждый сегмент | маленькая таблица в соединении |

`orders` (1 млн строк) распределена по `id`, `customers` - по `id`:

```sql
EXPLAIN SELECT o.id, c.name FROM orders o JOIN customers c ON o.customer_id = c.id;
```

```
 Gather Motion 16:1  (slice2; segments: 16)  (cost=0.00..920.98 rows=1000000 width=14)
   ->  Hash Join  (cost=0.00..886.17 rows=62500 width=14)
         Hash Cond: (orders.customer_id = customers.id)
         ->  Redistribute Motion 16:16  (slice1; segments: 16)  (cost=0.00..437.71 rows=62500 width=16)
               Hash Key: orders.customer_id
               ->  Seq Scan on orders  (cost=0.00..432.72 rows=62500 width=16)
         ->  Hash  (cost=431.15..431.15 rows=6250 width=14)
               ->  Seq Scan on customers  (cost=0.00..431.15 rows=6250 width=14)
 Optimizer: Pivotal Optimizer (GPORCA)
```

- `orders` распределена не по `customer_id`, поэтому ее строки пересылаются к нужным сегментам.
  После `ALTER TABLE orders SET DISTRIBUTED BY (customer_id)` тот же запрос идет без `Redistribute`:
  соединение локальное (co-located join).
- `rows` в узлах ниже `Gather Motion` - оценка на один сегмент: 1 млн / 16 = 62 500.
- ORCA пишет в плане имена таблиц (`orders.customer_id`), планировщик Postgres - псевдонимы (`o.customer_id`).
- **Slice** - кусок плана между motion; на каждом сегменте каждый slice выполняет отдельный процесс.
- `Broadcast Motion` появляется, когда маленькая таблица соединяется не по своему ключу распределения.
  `REPLICATED`-справочник уже лежит на каждом сегменте, и motion для него нет.
- Цена motion растет с числом сегментов: даже справочник из пары строк, пересылаемый на сотни сегментов,
  стоит заметного времени. Маленькие справочники делают `REPLICATED`.
- Последняя строка плана - какой оптимизатор его построил.

## EXPLAIN ANALYZE: факт по сегментам

Тот же `orders`, но половина заказов у одного клиента (`customer_id = 1`). Стоимости сокращены:

```
 Gather Motion 16:1  (slice2; segments: 16)  (... rows=20576 ...) (actual time=230.427..493.919 rows=50001 loops=1)
   ->  HashAggregate  (... rows=1286 ...) (actual time=220.237..221.005 rows=3249 loops=1)
         Group Key: orders.customer_id
         ->  Hash Join  (... rows=62500 ...) (actual time=3.598..219.317 rows=530930 loops=1)
               Hash Cond: (orders.customer_id = customers.id)
               Extra Text: (seg4)   Hash chain length 1.0 avg, 3 max, using 6110 of 262144 buckets.
               ->  Redistribute Motion 16:16  (slice1; segments: 16)  (... rows=62500 ...) (actual ... rows=530930 loops=1)
                     Hash Key: orders.customer_id
                     ->  Seq Scan on orders  (... rows=62500 ...) (actual time=0.018..10.067 rows=63087 loops=1)
 ...
   (slice1)    Executor memory: 58K bytes avg x 16 workers, 58K bytes max (seg0).
   (slice2)    Executor memory: 2944K bytes avg x 16 workers, 2944K bytes max (seg0).  Work_mem: 201K bytes max.
 Memory used:  128000kB
 Optimizer: Pivotal Optimizer (GPORCA)
 Execution time: 505.282 ms
```

- **`actual rows` - строки на самом загруженном сегменте**, оценка `rows` - на один сегмент в среднем.
  У `Gather Motion` на мастере `actual rows` - итог по всем сегментам.
- Перекос виден как разрыв: `Seq Scan` читает ровно (63 087 при оценке 62 500), а после `Redistribute`
  по `customer_id` на одном сегменте 530 930 строк - половина таблицы. `Extra Text: (seg4)` подсказывает,
  какой это сегмент. Такой же разрыв дает устаревшая статистика, поэтому проверить через `gp_segment_id`.
- `EXPLAIN (ANALYZE, VERBOSE)` добавляет память узла по сегментам:
  `Executor Memory: 3125kB  Segments: 16  Max: 201kB (segment 2)` и `Workfile: (0 spilling)`.
- Строки и время по каждому сегменту: `SET gp_enable_explain_allstat = on;` - у узлов появляется длинная
  строка `allstat: seg_firststart_total_ntuples/seg0_0.778 ms_6.381 ms_62406/seg1_...`.
- Звездочка `*` у slice и `Work_mem: ... wanted` в сноске - памяти не хватило, был spill.

## Оптимизаторы: ORCA и планировщик Postgres

- **ORCA (GPORCA)** - стоимостной оптимизатор для MPP, включен по умолчанию (`optimizer = on`). Сильнее
  на сложных запросах: разворачивает коррелированные подзапросы, отсекает партиции во время выполнения.
- **Планировщик Postgres (legacy)** - запасной. Если ORCA не поддерживает конструкцию, план тихо строит он:
  в плане `Optimizer: Postgres query optimizer`, в логе сообщение уровня LOG.
- Причину отката покажет `SET optimizer_trace_fallback = on;`:
  `INFO: GPORCA failed to produce a plan, falling back to planner`, `DETAIL: Feature not supported: LATERAL`.
- Откат бывает дорогим. Коррелированный подзапрос с равенством (`WHERE t.store_id = s.store_id`) ORCA
  превращает в соединение с группировкой, legacy выполняет его для каждой строки внешней таблицы: на 1 млн строк
  0,09 с против 4,8 с. С выражением в условии (`t.id % 1000 = s.store_id`) ORCA тоже оставляет подзапрос.
- `LATERAL` в Greenplum 6 всегда уходит в legacy.
- Откат случается и в функциях: после пяти вызовов Postgres кеширует общий план с параметрами, а такие планы
  ORCA не строит.
- Переключить для сессии: `SET optimizer = off;` - полезно, чтобы сравнить планы.
- **Статистика**: `ANALYZE таблица`. Автосбор (`gp_autostats_mode = on_no_stats`) срабатывает только для таблиц
  без статистики, а внутри функций он выключен (`gp_autostats_mode_in_functions = none`): после загрузки
  в функции `ANALYZE` вызывают явно. Без статистики оценки строк ошибаются в тысячи раз, и оптимизатор выбирает
  `Broadcast` огромной таблицы или неверный порядок соединений.

## Хранение: heap, AO, AOCS

| Тип | Как задать | Когда |
|---|---|---|
| heap | по умолчанию | частые `UPDATE`/`DELETE`, небольшие таблицы, как в Postgres |
| AO, append-optimized | `WITH (appendoptimized=true)` | пакетная загрузка и чтение; сжатие; изменение строк дорогое |
| AOCS, колоночное | `WITH (appendoptimized=true, orientation=column)` | широкие таблицы, запросы читают несколько колонок; лучшее сжатие |

```sql
CREATE TABLE fact_sales (id bigint, sale_date date, store_id int, amount numeric)
WITH (appendoptimized=true, orientation=column, compresstype=zstd, compresslevel=1)
DISTRIBUTED BY (id);
```

- `UPDATE` и `DELETE` в AO помечают строки скрытыми; место освобождает `VACUUM`, который переписывает файлы.
- В AOCS на каждую колонку свои файлы на каждом сегменте: колонки x партиции x сегменты дают очень много файлов.

## Партиционирование

```sql
CREATE TABLE sales (id bigint, sale_date date, amount numeric)
WITH (appendoptimized=true)
DISTRIBUTED BY (id)
PARTITION BY RANGE (sale_date)
(START (date '2026-01-01') INCLUSIVE END (date '2027-01-01') EXCLUSIVE EVERY (INTERVAL '1 month'));
```

- Партиции отсекаются по условию на колонку партиционирования. В плане ORCA это видно по строке
  `Partitions selected: 1 (out of 12)`, в `EXPLAIN ANALYZE` - `Partitions scanned: Avg 1.0 (out of 12)`.
  Legacy перечисляет `Seq Scan` по каждой оставшейся партиции.
- Отсечение ломают функция над колонкой (`date_trunc('month', sale_date) = ...`) и приведение колонки
  к другому типу (`sale_date::text = '2026-03-01'`): в обоих случаях 12 из 12. Сравнение с `now() - interval '10 days'`
  отсекает.
- ORCA отсекает и во время выполнения: `WHERE sale_date = (SELECT max(sale_date) FROM sales)` читает одну
  партицию. Legacy в этом случае читает все.
- Распределение - про то, на каком сегменте строка; партиции - про то, в каком файле внутри сегмента.
  Ключ распределения и ключ партиционирования обычно разные.
- Слишком много партиций раздувает каталог и замедляет планирование.

## Индексы

| | Postgres | Greenplum 6 |
|---|---|---|
| когда нужны | основной способ ускорить выборку | точечные запросы и малая доля строк; обычно быстрее параллельное полное чтение |
| типы | B-tree, Hash, GIN, GiST, SP-GiST, BRIN | B-tree, bitmap, GIN, GiST, SP-GiST; Hash и BRIN нет |
| построение без блокировки записи | `CREATE INDEX CONCURRENTLY` | нет |
| обычный | на любых колонках | на любых колонках |
| уникальный | на любых колонках | обязан включать все колонки ключа распределения: `(id, email)` можно, `(email)` нельзя |
| по выражению, частичный | работают | ORCA не использует; legacy использует индекс по выражению |
| AO, AOCS | - | работают, в плане `Bitmap Heap Scan` |

- Индекс не срабатывает: функция над колонкой (`lower(email) = ...` - нужен индекс `ON orders (lower(email))`),
  литерал другого типа (`id = 42.0` превращается в `(id)::numeric = 42.0`), условие выбирает большую долю строк
  (99 % - `Seq Scan`, 1 % - `Index Scan`).
- Составной индекс `(customer_id, created_at)` работает для условия на `customer_id` и на обе колонки, отдает
  `ORDER BY created_at` без сортировки. Условие только на `created_at` - `Seq Scan`.
- `INCLUDE` (PG 11+) дает `Index Only Scan` без чтения таблицы. `Heap Fetches` в плане растет после изменений,
  пока `VACUUM` не обновит карту видимости.
- Bitmap-индекс в Greenplum - для колонок с несколькими значениями. На 1 млн строк при 2 значениях - 2 МБ
  против 23 МБ у B-tree, при 100 000 значений - 6,5 ГБ.
- Индексы замедляют запись: 1 млн строк в AO с тремя индексами грузится 1,1 с, без них - 0,3 с. Перед большой
  загрузкой индексы удаляют и создают после. Неиспользуемые в Postgres - `pg_stat_user_indexes.idx_scan = 0`.

## Память, ресурсы, конкуренция

- Каждый запрос запускает процессы на всех сегментах для каждого slice. Тысячи мелких запросов - плохо
  для Greenplum, хорошо для Postgres.
- **Ресурсные очереди** (по умолчанию в GP6): `ACTIVE_STATEMENTS` - сколько запросов выполняется сразу,
  `MEMORY_LIMIT` - пропуск по памяти. **Ресурсные группы** - лимиты CPU и памяти через cgroups.
- Память запроса на сегменте - `statement_mem` (по умолчанию 125MB). Не хватает - запрос сбрасывает данные
  на диск (spill), запрос медленнее в разы. В `EXPLAIN ANALYZE` у сортировки
  `Sort Method:  external merge  Disk: 31744kB`, у `HashAggregate` - `62333 groups total in 32 batches; ... spill groups`,
  в сноске - `* (slice1) ... Work_mem: 2916K bytes max, 6353K bytes wanted`. При общей нехватке памяти
  на сегменте срабатывает защита и отменяет самый крупный запрос, необязательно виновника.
- Autovacuum для пользовательских таблиц в GP6 не работает: `VACUUM` и `ANALYZE` запускают по регламенту.
  Без этого раздуваются таблицы и системный каталог.

## Блокировки

Режимы блокировки таблицы, от слабого к сильному. Одинаковы в Postgres и Greenplum:

| Режим | Кто берет | С чем конфликтует |
|---|---|---|
| `AccessShareLock` | `SELECT` | `AccessExclusive` |
| `RowShareLock` | `SELECT ... FOR UPDATE / FOR SHARE` | `Exclusive`, `AccessExclusive` |
| `RowExclusiveLock` | `INSERT`, `UPDATE`, `DELETE` | `Share`, `ShareRowExclusive`, `Exclusive`, `AccessExclusive` |
| `ShareUpdateExclusiveLock` | `VACUUM`, `ANALYZE`, `CREATE INDEX CONCURRENTLY` | `ShareUpdateExclusive` и все сильнее |
| `ShareLock` | `CREATE INDEX` | `RowExclusive`, `ShareUpdateExclusive`, `ShareRowExclusive` и сильнее: стоит запись |
| `ShareRowExclusiveLock` | `CREATE TRIGGER`, добавление внешнего ключа | все, кроме `AccessShare` и `RowShare` |
| `ExclusiveLock` | `REFRESH MATERIALIZED VIEW CONCURRENTLY`; в Greenplum - `UPDATE`/`DELETE` в AO, `SELECT ... FOR UPDATE` | все, кроме `AccessShare`: идет только чтение |
| `AccessExclusiveLock` | `ALTER TABLE`, `DROP`, `TRUNCATE`, `VACUUM FULL`, `LOCK TABLE` | все, включая `SELECT` |

Что отличается по командам:

| Команда | Postgres | Greenplum 6 |
|---|---|---|
| `SELECT` | `AccessShareLock`, запись не ждет | так же |
| `INSERT` | `RowExclusiveLock` | так же, параллельные `INSERT` идут и в AO |
| `UPDATE`, `DELETE` в heap | блокируют строку | строку при включенном `gp_enable_global_deadlock_detector`, без него (по умолчанию) - всю таблицу |
| `UPDATE`, `DELETE` в AO, AOCS | - | всю таблицу (`ExclusiveLock`), ждет даже `INSERT` |
| `SELECT ... FOR UPDATE` | строки | всю таблицу; `SKIP LOCKED` нет, `NOWAIT` все равно ждет таблицу |
| `CREATE INDEX` | `ShareLock`: запись ждет | так же |
| `ALTER`, `TRUNCATE`, `DROP` | `AccessExclusiveLock`: ждут все, включая чтение | так же |

- Очередь блокировок: `ALTER` ждет конца долгого `SELECT`, а все новые запросы к таблице ждут `ALTER`.
  Для миграций - `SET lock_timeout = '1s'` и повтор.
- Взаимоблокировка: в Postgres и на одном сегменте Greenplum - `ERROR: deadlock detected` через `deadlock_timeout`
  (1 с); между сегментами - глобальный детектор раз в 2 мин. Лечение - менять строки в одном порядке и повторять транзакцию.
- Greenplum под ORCA: одновременный `UPDATE` одной строки - второй ждет первый и падает с
  `tuple to be updated was already moved to another segment due to concurrent update` (`UPDATE` = удаление + вставка,
  узел `Split`). С `optimizer = off` - как в Postgres.
- Очередь задач в Postgres (9.5+): `SELECT ... ORDER BY id LIMIT 10 FOR UPDATE SKIP LOCKED` - каждый обработчик
  берет свои строки.
- Кто кого ждет: в Postgres (9.6+) - `pg_stat_activity` и `pg_blocking_pids(pid)`. В Greenplum - `pg_locks WHERE NOT granted`
  (`gp_segment_id` - где ждет; ожидание строки на сегменте мастер в `pg_stat_activity` не показывает)
  и `gp_toolkit.gp_locks_on_relation`.

## Сводная таблица отличий

| | PostgreSQL | Greenplum 6 |
|---|---|---|
| назначение | OLTP, смешанная нагрузка | аналитика, большие объемы (OLAP) |
| масштабирование | вертикальное, реплики для чтения | горизонтальное: сегменты, `gpexpand` |
| ядро | актуальные версии | PostgreSQL 9.4 (GP7 - 12) |
| главное при проектировании | индексы | ключ распределения, тип хранения, партиции |
| индексы | основной инструмент | вторичны, чаще параллельное чтение всей таблицы; есть bitmap-индексы для колонок с малым числом значений |
| уникальность, внешние ключи | полноценные | `UNIQUE`/`PRIMARY KEY` только с ключом распределения, FK не проверяются |
| `UPDATE`/`DELETE` | обычные операции | на AO дорогие и блокируют таблицу целиком; на heap - так же без детектора |
| загрузка | `COPY`, `INSERT` | параллельно в сегменты: `gpfdist`, внешние таблицы, PXF |
| много мелких запросов | нормально | дорого: процессы на всех сегментах |
| обслуживание | autovacuum | `VACUUM` и `ANALYZE` вручную или по регламенту |

## Почему запрос медленный: чек-лист

1. Последняя строка `EXPLAIN`: ORCA или откат на planner Postgres.
2. Motion: `Redistribute` или `Broadcast` больших таблиц - ключи распределения не совпадают с ключом соединения,
   маленькие справочники не `REPLICATED`.
3. Перекос: в `EXPLAIN ANALYZE` `actual rows` (самый загруженный сегмент) во много раз больше оценки `rows`
   на сегмент; проверка через `gp_segment_id`.
4. Статистика: оценка строк против факта в `EXPLAIN ANALYZE`; `ANALYZE` после загрузки.
5. Spill на диск: `*` у slice, `Work_mem ... wanted`, `external merge  Disk`, `spill groups` - мало `statement_mem`.
6. Партиции: отсекаются ли (`Partitions selected` / `Partitions scanned`).
7. Раздутие: давно не было `VACUUM`, много скрытых строк в AO.
8. Очередь: запрос ждет слота в ресурсной очереди, а не выполняется (`pg_stat_activity`, `gp_toolkit.gp_resqueue_status`).
9. Блокировка: запрос ждет чужую транзакцию (`pg_locks WHERE NOT granted`, `gp_toolkit.gp_locks_on_relation`).
