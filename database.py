import sqlite3
from datetime import datetime, timedelta
import random

def create_database():
    conn = sqlite3.connect("techcorp.db")
    cursor = conn.cursor()

    # ── Create Tables ─────────────────────────────────────
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS departments (
        id         INTEGER PRIMARY KEY,
        name       TEXT NOT NULL,
        budget     REAL NOT NULL,
        manager    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS employees (
        id          INTEGER PRIMARY KEY,
        name        TEXT NOT NULL,
        department  TEXT NOT NULL,
        salary      REAL NOT NULL,
        hire_date   TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS products (
        id       INTEGER PRIMARY KEY,
        name     TEXT NOT NULL,
        category TEXT NOT NULL,
        price    REAL NOT NULL,
        stock    INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sales (
        id          INTEGER PRIMARY KEY,
        product_id  INTEGER NOT NULL,
        employee_id INTEGER NOT NULL,
        amount      REAL NOT NULL,
        sale_date   TEXT NOT NULL,
        FOREIGN KEY (product_id)  REFERENCES products(id),
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    );
    """)

    # ── Insert Departments ────────────────────────────────
    departments = [
        (1, "Engineering",  500000, "Sarah Johnson"),
        (2, "Sales",        300000, "Ahmed Khan"),
        (3, "Marketing",    200000, "Lisa Chen"),
        (4, "HR",           150000, "Omar Farooq"),
        (5, "Finance",      250000, "Maria Garcia"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO departments VALUES (?,?,?,?)",
        departments
    )

    # ── Insert Employees ──────────────────────────────────
    employees = [
        (1,  "Sarah Johnson",  "Engineering", 95000, "2019-03-15"),
        (2,  "Ahmed Khan",     "Sales",        88000, "2020-06-01"),
        (3,  "Lisa Chen",      "Marketing",    82000, "2018-11-20"),
        (4,  "Omar Farooq",    "Engineering",  78000, "2021-01-10"),
        (5,  "Maria Garcia",   "Finance",      91000, "2017-08-05"),
        (6,  "James Wilson",   "Sales",        65000, "2022-03-22"),
        (7,  "Aisha Malik",    "HR",           60000, "2021-09-14"),
        (8,  "David Park",     "Engineering",  85000, "2020-02-28"),
        (9,  "Zara Ahmed",     "Marketing",    58000, "2023-01-05"),
        (10, "Carlos Rivera",  "Finance",      72000, "2019-07-19"),
        (11, "Emma Thompson",  "Engineering",  76000, "2021-04-30"),
        (12, "Bilal Hassan",   "Sales",        61000, "2022-08-11"),
        (13, "Sophie Turner",  "HR",           55000, "2023-03-01"),
        (14, "Ryan O'Brien",   "Marketing",    63000, "2020-10-15"),
        (15, "Fatima Zahra",   "Finance",      69000, "2018-05-22"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO employees VALUES (?,?,?,?,?)",
        employees
    )

    # ── Insert Products ───────────────────────────────────
    products = [
        (1,  "Laptop Pro",      "Electronics",  1299.99, 45),
        (2,  "Wireless Mouse",  "Electronics",    29.99, 200),
        (3,  "Standing Desk",   "Furniture",     499.99,  30),
        (4,  "Monitor 4K",      "Electronics",   399.99,  60),
        (5,  "Office Chair",    "Furniture",     299.99,  25),
        (6,  "Keyboard",        "Electronics",    79.99, 150),
        (7,  "Webcam HD",       "Electronics",    89.99,  80),
        (8,  "Notebook Pack",   "Stationery",      9.99, 500),
        (9,  "Headphones",      "Electronics",   149.99,  70),
        (10, "Desk Lamp",       "Furniture",      49.99, 120),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO products VALUES (?,?,?,?,?)",
        products
    )

    # ── Insert Sales (random but realistic) ───────────────
    random.seed(42)
    sales = []
    base_date = datetime(2024, 1, 1)
    for i in range(1, 101):
        sale_date   = base_date + timedelta(days=random.randint(0, 364))
        product_id  = random.randint(1, 10)
        employee_id = random.randint(1, 15)
        amount      = round(random.uniform(500, 5000), 2)
        sales.append((i, product_id, employee_id, amount,
                       sale_date.strftime("%Y-%m-%d")))

    cursor.executemany(
        "INSERT OR IGNORE INTO sales VALUES (?,?,?,?,?)",
        sales
    )

    conn.commit()
    conn.close()
    print("[database] TechCorp database created ✅")

if __name__ == "__main__":
    create_database()