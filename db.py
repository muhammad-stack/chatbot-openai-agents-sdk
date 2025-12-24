import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OrderTotals:
    subtotal: int
    delivery_fee: int
    tax: int
    total: int


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            status TEXT NOT NULL,
            delivery_type TEXT NOT NULL, -- delivery | pickup
            address TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            item_type TEXT NOT NULL, -- pizza | extra
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            size TEXT,
            qty INTEGER NOT NULL,
            unit_price INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS order_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def create_customer(conn: sqlite3.Connection, name: str, phone: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO customers(name, phone, created_at) VALUES (?, ?, ?)",
        (name.strip(), (phone or "").strip() or None, utc_now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def create_order(
    conn: sqlite3.Connection,
    customer_id: int | None,
    delivery_type: str,
    address: str | None = None,
    notes: str | None = None,
) -> int:
    now = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO orders(customer_id, status, delivery_type, address, notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (customer_id, "draft", delivery_type, address, notes, now, now),
    )
    order_id = int(cur.lastrowid)
    conn.execute(
        "INSERT INTO order_updates(order_id, status, message, created_at) VALUES (?, ?, ?, ?)",
        (order_id, "draft", "Order created", now),
    )
    conn.commit()
    return order_id


def add_order_item(
    conn: sqlite3.Connection,
    order_id: int,
    item_type: str,
    item_id: str,
    item_name: str,
    qty: int,
    unit_price: int,
    size: str | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO order_items(order_id, item_type, item_id, item_name, size, qty, unit_price, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            item_type,
            item_id,
            item_name,
            size,
            int(qty),
            int(unit_price),
            utc_now_iso(),
        ),
    )
    conn.execute("UPDATE orders SET updated_at=? WHERE id=?", (utc_now_iso(), order_id))
    conn.commit()
    return int(cur.lastrowid)


def remove_order_item(conn: sqlite3.Connection, order_item_id: int) -> None:
    conn.execute("DELETE FROM order_items WHERE id=?", (int(order_item_id),))
    conn.commit()


def set_order_status(conn: sqlite3.Connection, order_id: int, status: str, message: str | None = None) -> None:
    now = utc_now_iso()
    conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (status, now, int(order_id)))
    conn.execute(
        "INSERT INTO order_updates(order_id, status, message, created_at) VALUES (?, ?, ?, ?)",
        (int(order_id), status, message, now),
    )
    conn.commit()


def get_order(conn: sqlite3.Connection, order_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM orders WHERE id=?", (int(order_id),)).fetchone()
    if row is None:
        return None
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id=? ORDER BY id ASC", (int(order_id),)
    ).fetchall()
    updates = conn.execute(
        "SELECT * FROM order_updates WHERE order_id=? ORDER BY id ASC", (int(order_id),)
    ).fetchall()
    return {
        "order": dict(row),
        "items": [dict(i) for i in items],
        "updates": [dict(u) for u in updates],
    }


def list_orders(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (int(limit),)
    ).fetchall()
    return [dict(r) for r in rows]


def compute_totals(
    items: Iterable[dict[str, Any]],
    delivery_fee: int,
    tax_percent: float,
) -> OrderTotals:
    subtotal = 0
    for item in items:
        subtotal += int(item["qty"]) * int(item["unit_price"])
    tax = int(round(subtotal * float(tax_percent)))
    total = subtotal + int(delivery_fee) + tax
    return OrderTotals(subtotal=subtotal, delivery_fee=int(delivery_fee), tax=tax, total=total)
