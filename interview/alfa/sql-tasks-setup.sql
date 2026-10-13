-- Данные для задач из sql-tasks.md. Любой Postgres 12+, запускать целиком.
DROP TABLE IF EXISTS employees, departments, payments, orders, logins;

CREATE TABLE departments (
    id   INT PRIMARY KEY,
    name TEXT NOT NULL
);
INSERT INTO departments VALUES
    (1, 'Разработка'),
    (2, 'Аналитика'),
    (3, 'Продажи'),
    (4, 'Юристы');

CREATE TABLE employees (
    id         INT PRIMARY KEY,
    name       TEXT NOT NULL,
    dept_id    INT REFERENCES departments (id),
    manager_id INT REFERENCES employees (id),
    salary     INT NOT NULL
);
INSERT INTO employees VALUES
    (1,  'Анна',   1,    NULL, 300000),
    (2,  'Борис',  1,    1,    250000),
    (3,  'Вера',   1,    1,    250000),
    (4,  'Глеб',   1,    2,    300000),
    (5,  'Дина',   1,    2,    180000),
    (6,  'Егор',   2,    1,    220000),
    (7,  'Жанна',  2,    6,    230000),
    (8,  'Захар',  2,    6,    150000),
    (9,  'Ирина',  3,    1,    200000),
    (10, 'Кирилл', 3,    9,    120000),
    (11, 'Лена',   3,    9,    120000),
    (12, 'Марк',   NULL, 1,    100000);

CREATE TABLE payments (
    id        INT PRIMARY KEY,
    client_id INT NOT NULL,
    paid_at   TIMESTAMP NOT NULL,
    amount    NUMERIC(15, 2) NOT NULL
);
INSERT INTO payments VALUES
    (1, 101, '2026-10-01 10:00', 500),
    (2, 101, '2026-10-01 10:00', 500),
    (3, 102, '2026-10-01 11:00', 700),
    (4, 103, '2026-10-02 09:30', 300),
    (5, 103, '2026-10-02 09:30', 300),
    (6, 103, '2026-10-02 09:30', 300),
    (7, 101, '2026-10-03 12:00', 500);

CREATE TABLE orders (
    id         INT PRIMARY KEY,
    order_date DATE NOT NULL,
    amount     NUMERIC(15, 2) NOT NULL
);
INSERT INTO orders VALUES
    (1, '2026-09-29', 1000),
    (2, '2026-09-29', 500),
    (3, '2026-09-30', 700),
    (4, '2026-10-01', 200),
    (5, '2026-10-01', 300),
    (6, '2026-10-03', 1000),
    (7, '2026-10-04', 400);

CREATE TABLE logins (
    user_id    INT NOT NULL,
    login_date DATE NOT NULL
);
INSERT INTO logins VALUES
    (1, '2026-10-01'), (1, '2026-10-02'), (1, '2026-10-03'), (1, '2026-10-05'), (1, '2026-10-06'),
    (2, '2026-10-01'), (2, '2026-10-01'), (2, '2026-10-02'),
    (2, '2026-10-04'), (2, '2026-10-05'), (2, '2026-10-06'), (2, '2026-10-07'),
    (3, '2026-10-02');
