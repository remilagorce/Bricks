#!/usr/bin/env python3
"""Bricks db.py — the single write door to a workspace database.

Stdlib only. Runs from the workspace root: python3 tools/db.py <command> ...

Commands:
  init                          create bricks.db from schema.sql (idempotent)
  seed --csv FILE               upsert companies from a CSV (columns: name,domain)
  select TABLE [--where W] [--cols C] [--limit N]     rows as JSON (for bricks)
  insert TABLE --set k=v [--set k=v ...]              returns {"id": n}
  upsert TABLE --key COL --set k=v [...]              insert or update on key conflict
  write TABLE ID --set k=v [--set k=v ...]            update one row + updated_at
  count TABLE [--where W]                             returns {"count": n}
  show [TABLE] [--where W] [--limit N]                human-readable table

Notes:
- --where takes raw SQL. This is a local, single-user tool operating on the
  workspace database; keep values simple and quoted.
- Identifiers (table, columns) are validated against an allowlist pattern.
"""

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

DB_FILE = "bricks.db"
TABLES = ("companies", "people", "messages")
IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def die(msg):
    print(json.dumps({"error": msg}), file=sys.stderr)
    sys.exit(1)


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def connect(db_path):
    fresh = not os.path.exists(db_path)
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    con.execute("PRAGMA foreign_keys=ON")
    if fresh:
        con.executescript(load_schema())
        con.commit()
    return con


def load_schema():
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    if not os.path.exists(schema_path):
        die(f"schema.sql not found next to db.py ({schema_path})")
    with open(schema_path, encoding="utf-8") as f:
        return f.read()


def check_table(table):
    if table not in TABLES:
        die(f"unknown table '{table}' (allowed: {', '.join(TABLES)})")
    return table


def parse_sets(pairs):
    sets = {}
    for pair in pairs or []:
        if "=" not in pair:
            die(f"bad --set '{pair}', expected field=value")
        field, value = pair.split("=", 1)
        field = field.strip()
        if not IDENT_RE.match(field):
            die(f"bad field name '{field}'")
        sets[field] = None if value == "NULL" else value
    if not sets:
        die("at least one --set field=value is required")
    return sets


def cmd_init(args):
    con = sqlite3.connect(args.db, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(load_schema())
    con.commit()
    con.close()
    print(json.dumps({"ok": True, "db": args.db}))


def cmd_seed(args):
    con = connect(args.db)
    created, skipped = 0, 0
    with open(args.csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("name") or "").strip()
            domain = (row.get("domain") or "").strip().lower() or None
            if not name:
                continue
            try:
                con.execute(
                    "INSERT INTO companies (name, domain, source) VALUES (?, ?, 'seed')",
                    (name, domain),
                )
                created += 1
            except sqlite3.IntegrityError:
                skipped += 1
    con.commit()
    con.close()
    print(json.dumps({"created": created, "duplicates_skipped": skipped}))


def build_query(table, cols, where, limit):
    if cols:
        col_list = [c.strip() for c in cols.split(",")]
        for c in col_list:
            if not IDENT_RE.match(c):
                die(f"bad column name '{c}'")
        select_cols = ", ".join(col_list)
    else:
        select_cols = "*"
    query = f"SELECT {select_cols} FROM {table}"
    if where:
        query += f" WHERE {where}"
    query += " ORDER BY id"
    if limit:
        query += f" LIMIT {int(limit)}"
    return query


def cmd_select(args):
    table = check_table(args.table)
    con = connect(args.db)
    try:
        rows = con.execute(build_query(table, args.cols, args.where, args.limit)).fetchall()
    except sqlite3.Error as e:
        die(f"sql error: {e}")
    con.close()
    print(json.dumps([dict(r) for r in rows], ensure_ascii=False))


def cmd_insert(args):
    table = check_table(args.table)
    sets = parse_sets(args.set)
    con = connect(args.db)
    fields = ", ".join(sets)
    marks = ", ".join("?" for _ in sets)
    try:
        cur = con.execute(
            f"INSERT INTO {table} ({fields}) VALUES ({marks})", list(sets.values())
        )
        con.commit()
    except sqlite3.Error as e:
        die(f"sql error: {e}")
    print(json.dumps({"id": cur.lastrowid}))
    con.close()


def cmd_upsert(args):
    table = check_table(args.table)
    key = args.key.strip()
    if not IDENT_RE.match(key):
        die(f"bad key column '{key}'")
    sets = parse_sets(args.set)
    if key not in sets:
        die(f"--set must include the key column '{key}'")
    con = connect(args.db)
    row = con.execute(
        f"SELECT id FROM {table} WHERE {key} = ?", (sets[key],)
    ).fetchone()
    if row:
        assignments = ", ".join(f"{f} = ?" for f in sets)
        con.execute(
            f"UPDATE {table} SET {assignments}, updated_at = ? WHERE id = ?",
            list(sets.values()) + [now_utc(), row["id"]],
        )
        con.commit()
        print(json.dumps({"id": row["id"], "created": False}))
    else:
        fields = ", ".join(sets)
        marks = ", ".join("?" for _ in sets)
        cur = con.execute(
            f"INSERT INTO {table} ({fields}) VALUES ({marks})", list(sets.values())
        )
        con.commit()
        print(json.dumps({"id": cur.lastrowid, "created": True}))
    con.close()


def cmd_write(args):
    table = check_table(args.table)
    sets = parse_sets(args.set)
    con = connect(args.db)
    assignments = ", ".join(f"{f} = ?" for f in sets)
    try:
        cur = con.execute(
            f"UPDATE {table} SET {assignments}, updated_at = ? WHERE id = ?",
            list(sets.values()) + [now_utc(), args.id],
        )
        con.commit()
    except sqlite3.Error as e:
        die(f"sql error: {e}")
    if cur.rowcount == 0:
        die(f"no row with id={args.id} in {table}")
    print(json.dumps({"updated": cur.rowcount, "id": args.id}))
    con.close()


def cmd_count(args):
    table = check_table(args.table)
    con = connect(args.db)
    query = f"SELECT COUNT(*) AS n FROM {table}"
    if args.where:
        query += f" WHERE {args.where}"
    try:
        n = con.execute(query).fetchone()["n"]
    except sqlite3.Error as e:
        die(f"sql error: {e}")
    con.close()
    print(json.dumps({"count": n}))


def cmd_show(args):
    tables = [check_table(args.table)] if args.table else list(TABLES)
    con = connect(args.db)
    for table in tables:
        rows = con.execute(
            build_query(table, None, args.where if args.table else None, args.limit or 50)
        ).fetchall()
        print(f"\n== {table} ({len(rows)} shown) ==")
        if not rows:
            continue
        cols = rows[0].keys()
        widths = {
            c: min(28, max(len(c), max(len(str(r[c] or "")) for r in rows)))
            for c in cols
        }
        print("  ".join(c.ljust(widths[c]) for c in cols))
        for r in rows:
            print(
                "  ".join(
                    str(r[c] if r[c] is not None else "-")[: widths[c]].ljust(widths[c])
                    for c in cols
                )
            )
    con.close()


def main():
    parser = argparse.ArgumentParser(description="Bricks workspace database CLI")
    parser.add_argument("--db", default=DB_FILE, help=f"database path (default: {DB_FILE})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")

    p = sub.add_parser("seed")
    p.add_argument("--csv", required=True)

    p = sub.add_parser("select")
    p.add_argument("table")
    p.add_argument("--where")
    p.add_argument("--cols")
    p.add_argument("--limit", type=int)

    p = sub.add_parser("insert")
    p.add_argument("table")
    p.add_argument("--set", action="append")

    p = sub.add_parser("upsert")
    p.add_argument("table")
    p.add_argument("--key", required=True)
    p.add_argument("--set", action="append")

    p = sub.add_parser("write")
    p.add_argument("table")
    p.add_argument("id", type=int)
    p.add_argument("--set", action="append")

    p = sub.add_parser("count")
    p.add_argument("table")
    p.add_argument("--where")

    p = sub.add_parser("show")
    p.add_argument("table", nargs="?")
    p.add_argument("--where")
    p.add_argument("--limit", type=int)

    args = parser.parse_args()
    {
        "init": cmd_init,
        "seed": cmd_seed,
        "select": cmd_select,
        "insert": cmd_insert,
        "upsert": cmd_upsert,
        "write": cmd_write,
        "count": cmd_count,
        "show": cmd_show,
    }[args.command](args)


if __name__ == "__main__":
    main()
