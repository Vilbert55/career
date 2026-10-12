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

**Postgres.** Типы:

| Тип | Для чего |
|---|---|
| B-tree | по умолчанию: `=`, диапазоны, `ORDER BY`, префикс `LIKE 'abc%'` |
| Hash | только `=` |
| GIN | много значений в одной строке: массивы, `jsonb`, полнотекстовый поиск |
| GiST, SP-GiST | геометрия, диапазоны, поиск ближайших |
| BRIN | огромные таблицы, где значение следует физическому порядку строк (время вставки) |

Тестовая таблица `orders` на 1 млн строк, индекс `(customer_id, created_at)`:

- Условие на `customer_id` или на обе колонки - индекс работает. `WHERE customer_id = 42 ORDER BY created_at DESC
  LIMIT 5` идет без сортировки: `Index Scan Backward`. Условие только на `created_at` - `Seq Scan`:
  в составном индексе важен порядок колонок.
- Индекс не используется, когда:
  - над колонкой функция: `lower(email) = ...` - нужен индекс по выражению `ON orders (lower(email))`;
  - литерал другого типа: `id = 42.0` превращается в `(id)::numeric = 42.0` и дает `Seq Scan`, `id = '42'` работает;
  - `LIKE 'user42%'` при collation, отличной от C (`en_US.utf8`), - нужен индекс с `text_pattern_ops`;
    `LIKE '%42'` B-tree не ускоряет совсем;
  - условие выбирает большую долю строк: `status = 'done'` (99 %) - `Seq Scan`, `status = 'new'` (1 %) - `Index Scan`.
- Частичный индекс `ON orders (created_at) WHERE status = 'new'` - маленький индекс под частый фильтр по редкому значению.
- Покрывающий индекс `ON orders (customer_id) INCLUDE (amount)` (PG 11+) дает `Index Only Scan`, таблица
  не читается. `Heap Fetches` в плане - сколько раз все же пришлось читать таблицу: после `UPDATE` половины строк
  стало 20 вместо 0, пока `VACUUM` не обновит карту видимости.
- Условие с `OR` по двум колонкам с индексами - `BitmapOr` из двух `Bitmap Index Scan`.
- `CREATE INDEX` берет `ShareLock`: чтение идет, запись ждет конца построения. `CREATE INDEX CONCURRENTLY`
  запись не блокирует, строит дольше и не запускается внутри транзакции.
- Каждый индекс замедляет `INSERT` и `UPDATE` и занимает место: 9 индексов на тестовой таблице - 329 МБ
  при таблице 121 МБ. Неиспользуемые находят по `pg_stat_user_indexes.idx_scan = 0`.

**Greenplum 6.** Индекс строится на каждом сегменте по его части строк. Greenplum рассчитан на параллельное
полное чтение, индексы нужны для точечных запросов и выборки малой доли строк из большой таблицы.

- Есть B-tree, bitmap, GiST, GIN, SP-GiST. Hash - `ERROR: hash indexes are not supported`, BRIN нет (он с PG 9.5).
- `CREATE INDEX CONCURRENTLY` не поддерживается.
- Уникальный индекс обязан содержать ключ распределения.
- Индексы на AO и AOCS работают; в плане `Bitmap Heap Scan`. На heap ORCA выбирает `Index Scan`.
- Равенство по ключу распределения отправляет запрос на один сегмент: `Gather Motion 1:1  (slice1; segments: 1)`.
- ORCA в 6.21 не использует индексы по выражению и частичные индексы - в плане `Seq Scan`. Legacy индекс
  по выражению использует.
- `CREATE INDEX` на партиционированной таблице создает индекс на каждой партиции (12 из 12).
- Индексы замедляют загрузку: 1 млн строк в AO без индексов - 0,3 с, с тремя индексами - 1,1 с. Перед большой
  загрузкой индексы удаляют и создают заново после нее.
- **Bitmap-индекс** - для колонок с несколькими значениями. Размер на 1 млн строк:

| Различных значений | bitmap | B-tree |
|---|---|---|
| 2 | 2 МБ | 23 МБ |
| 1 000 | 502 МБ | 23 МБ |
| 100 000 | 6,5 ГБ | 23 МБ |
| 1 000 000 | 486 МБ | 23 МБ |

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

**Postgres.** MVCC: чтение не ждет запись, запись не ждет чтение. `SELECT` строки, которую меняет чужая
незавершенная транзакция, сразу отдает старую версию.

- Запись ждет запись: второй `UPDATE` той же строки ждет коммита или отката первой транзакции, затем применяется
  к новой версии строки (Read Committed). `UPDATE` другой строки не ждет.
- Блокировки таблицы, которые берут команды:

| Команда | Режим | Кого блокирует |
|---|---|---|
| `SELECT` | `AccessShareLock` | только `AccessExclusive`: `ALTER`, `DROP`, `TRUNCATE`, `VACUUM FULL` |
| `SELECT ... FOR UPDATE` | `RowShareLock` | на таблице - только DDL; выбранные строки - как `UPDATE` |
| `INSERT`, `UPDATE`, `DELETE` | `RowExclusiveLock` | `CREATE INDEX` и DDL |
| `ANALYZE`, `VACUUM` | `ShareUpdateExclusiveLock` | друг друга, `CREATE INDEX` и DDL |
| `CREATE INDEX` | `ShareLock` | запись в таблицу |
| `ALTER TABLE`, `TRUNCATE`, `DROP` | `AccessExclusiveLock` | всех, включая чтение |

- **Очередь блокировок.** `ALTER TABLE` ждет конца долгого `SELECT`, и все новые запросы к таблице встают
  в очередь за `ALTER`. В тесте `SELECT` одной строки ждал 3,6 с. Для миграций - `SET lock_timeout = '1s'` и повтор:
  `ALTER` падает с `canceling statement due to lock timeout`, остальные запросы идут.
- **Взаимоблокировка** - две транзакции меняют строки 10 и 20 в разном порядке. Через `deadlock_timeout` (1 с)
  одна получает `ERROR: deadlock detected`. Лечение - менять строки в одном порядке и повторять транзакцию.
- **Очередь задач на таблице.** `SELECT id FROM orders WHERE status = 'new' ORDER BY id LIMIT 3 FOR UPDATE SKIP LOCKED`
  (PG 9.5+): каждый обработчик получает свои строки, первый - 100, 200, 300, второй - 400, 500, 600.
  Без `SKIP LOCKED` второй ждет. С `NOWAIT` - сразу `ERROR: could not obtain lock on row`.
- Кто кого держит (PG 9.6+):

```sql
SELECT pid, wait_event_type, wait_event, pg_blocking_pids(pid) AS blocked_by, query
FROM pg_stat_activity
WHERE wait_event_type = 'Lock';
-- ожидание строки: wait_event = transactionid; таблицы: wait_event = relation
```

- `pg_cancel_backend(pid)` отменяет запрос, `pg_terminate_backend(pid)` закрывает сессию.

**Greenplum 6.** Блокировки берутся на мастере и на сегментах. `pg_locks` показывает все, колонка
`gp_segment_id` (-1 - мастер). Главное отличие - блокировки всей таблицы там, где Postgres блокирует строку:

| Команда | Блокировка | Следствие |
|---|---|---|
| `UPDATE`, `DELETE` в heap | `RowExclusiveLock` при включенном `gp_enable_global_deadlock_detector` | разные строки меняются параллельно; без детектора (по умолчанию в GP6 выключен) - `ExclusiveLock` на всю таблицу |
| `UPDATE`, `DELETE` в AO, AOCS | `ExclusiveLock` на мастере | ждут все изменения таблицы, включая `INSERT`; чтение идет |
| `SELECT ... FOR UPDATE` | `ExclusiveLock` на мастере | ждут `UPDATE` и `FOR UPDATE` любых строк таблицы |
| `INSERT` | `RowExclusiveLock` | параллельные `INSERT` не ждут друг друга, в AO тоже |

- **Одновременный `UPDATE` одной строки под ORCA падает.** ORCA строит `UPDATE` как удаление плюс вставку
  (узел `Split` в плане). Вторая транзакция ждет первую, затем получает
  `ERROR: tuple to be updated was already moved to another segment due to concurrent update`. С `optimizer = off`
  она дожидается и применяет изменение поверх, как в Postgres. Код, который правит одни и те же строки,
  должен повторять транзакцию.
- `SKIP LOCKED` нет (синтаксис PG 9.5). `NOWAIT` не помогает: `FOR UPDATE` сначала ждет блокировку таблицы.
- Взаимоблокировку на одном сегменте снимает обычный детектор за `deadlock_timeout` (1 с). Между сегментами -
  глобальный детектор, он проверяет раз в `gp_global_deadlock_detector_period` (2 мин). В тесте снял через 98 с:
  `canceling statement due to user request: "cancelled by global deadlock detector"`.
- `pg_blocking_pids` нет. На мастере `pg_stat_activity.waiting = t` и `waiting_reason = lock` видны только
  для ожидания на мастере (блокировка таблицы). Ожидание строки идет на сегменте: на мастере `waiting = f`, найти его можно
  только в `pg_locks`:

```sql
SELECT locktype, mode, gp_segment_id, pid, mppsessionid FROM pg_locks WHERE NOT granted;
-- transactionid | ShareLock | 4 | ...  - ждет строку на сегменте 4

SELECT lorpid, lormode, lorgranted, lorcurrentquery          -- держатель и ожидающий с текстом запроса
FROM gp_toolkit.gp_locks_on_relation WHERE lorrelname = 'orders';
```

- `lock_timeout` работает, ошибка приходит с сегмента: `canceling statement due to lock timeout (seg4 ...)`.

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
