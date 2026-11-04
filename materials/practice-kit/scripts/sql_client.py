"""Закрытый semantic layer с AST: произвольный SQL принципиально не допускается."""

import json
import re
from pathlib import Path

import psycopg
import sqlglot
from sqlglot import exp

TEMPLATES = {
    "status": """
        SELECT order_id, status
          FROM training_api.allowed_orders_a
         WHERE order_id = %s
         LIMIT 20
    """,
    # PostgreSQL GREATEST игнорирует NULL. Без явного фильтра неизвестный
    # остаток дал бы ложный нулевой дефицит; такой случай не выдаём как расчёт.
    "shortage": """
        SELECT order_id,
               GREATEST(ordered - available, 0) AS shortage,
               unit
          FROM training_api.allowed_orders_a
         WHERE order_id = %s
           AND available IS NOT NULL
         LIMIT 20
    """,
}


def ast_guard(candidate, operation):
    """Сравнение полного AST с серверным шаблоном. Параметр показан как :order_id."""
    approved = TEMPLATES[operation].replace("%s", ":order_id")
    expressions = sqlglot.parse(candidate, read="postgres")
    if len(expressions) != 1 or type(expressions[0]) is not exp.Select:
        raise ValueError("one SELECT required")
    if expressions[0] != sqlglot.parse_one(approved, read="postgres"):
        raise ValueError("outside approved semantic operation")
    return True


def execute(operation, order_id, actor="reader-a"):
    if (
        actor != "reader-a"
        or operation not in TEMPLATES
        or not re.fullmatch(r"TRN-\d{4}", order_id)
    ):
        raise PermissionError("not permitted")
    query = TEMPLATES[operation]
    ast_guard(query.replace("%s", ":order_id"), operation)
    password = Path("/run/secrets/db-reader.txt").read_text().strip()
    with psycopg.connect(
        host="db",
        dbname="training",
        user="reader_a",
        password=password,
        connect_timeout=3,
    ) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout='2s'")
            connection.execute("SET LOCAL lock_timeout='500ms'")
            return connection.execute(query, (order_id,)).fetchmany(20)


if __name__ == "__main__":
    outputs = {
        f"{op}-{ident}": execute(op, ident)
        for op in TEMPLATES
        for ident in ["TRN-0001", "TRN-0002", "TRN-0003", "TRN-0004"]
    }
    # Данные синтетические; в промышленном аудите сохраняют ID/исход, а не SQL-результат.
    print(json.dumps(outputs, ensure_ascii=False, default=str, indent=2))
