import csv
import glob
import os
import getpass

import duckdb
import psycopg
from psycopg import sql

DB_NAME = "pulseiq_wh"
SCHEMA = "dw"
CLEAN_DIR = os.path.join("reports", "clean")

TYPE_MAP = {
    "VARCHAR": "TEXT",
    "BIGINT": "BIGINT",
    "INTEGER": "INTEGER",
    "SMALLINT": "SMALLINT",
    "TINYINT": "SMALLINT",
    "DOUBLE": "DOUBLE PRECISION",
    "FLOAT": "REAL",
    "REAL": "REAL",
    "BOOLEAN": "BOOLEAN",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
    "TIMESTAMP WITHOUT TIME ZONE": "TIMESTAMP",
    "TIME": "TIME",
    "BLOB": "BYTEA",
}

def postgres_type(dtype):
    dtype = dtype.upper().strip()
    if dtype.startswith("DECIMAL") or dtype.startswith("NUMERIC"):
        return "NUMERIC"
    if dtype.startswith("TIMESTAMP WITH TIME ZONE"):
        return "TIMESTAMPTZ"
    if dtype.startswith("TIMESTAMP"):
        return "TIMESTAMP"
    if dtype.startswith("VARCHAR") or dtype.startswith("CHAR"):
        return "TEXT"
    if dtype.startswith("UBIGINT") or dtype.startswith("HUGEINT"):
        return "NUMERIC"
    if dtype in TYPE_MAP:
        return TYPE_MAP[dtype]
    raise ValueError("Unsupported DuckDB type: " + dtype)

def main():
    files = sorted(glob.glob(os.path.join(CLEAN_DIR, "*_clean.csv")))
    if not files:
        raise FileNotFoundError("No clean CSV files found in reports/clean")

    password = getpass.getpass("PostgreSQL password: ")
    duck = duckdb.connect("pulseiq.duckdb", read_only=True)
    conn = psycopg.connect(
        host="localhost", dbname=DB_NAME,
        user="postgres", password=password
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = %s", (SCHEMA,)
            )
            existing = [row[0] for row in cur.fetchall()]
            if existing:
                raise RuntimeError(
                    "dw schema is not empty; stopped to protect data: "
                    + ", ".join(existing)
                )

            for path in files:
                table = os.path.basename(path).replace("_clean.csv", "")
                description = duck.execute(
                    f'DESCRIBE raw."{table}"'
                ).fetchall()
                names = [row[0] for row in description]
                definitions = [
                    sql.SQL("{} {}").format(
                        sql.Identifier(row[0]),
                        sql.SQL(postgres_type(row[1]))
                    )
                    for row in description
                ]

                cur.execute(sql.SQL("CREATE TABLE {}.{} ({})").format(
                    sql.Identifier(SCHEMA),
                    sql.Identifier(table),
                    sql.SQL(", ").join(definitions)
                ))

                copy_command = sql.SQL(
                    "COPY {}.{} ({}) FROM STDIN "
                    "WITH (FORMAT CSV, HEADER TRUE, NULL '')"
                ).format(
                    sql.Identifier(SCHEMA),
                    sql.Identifier(table),
                    sql.SQL(", ").join(sql.Identifier(n) for n in names)
                )

                with open(path, "r", encoding="utf-8-sig", newline="") as f:
                    with cur.copy(copy_command) as copy:
                        while True:
                            chunk = f.read(1024 * 1024)
                            if not chunk:
                                break
                            copy.write(chunk)

                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
                    sql.Identifier(SCHEMA), sql.Identifier(table)
                ))
                print(table + ": " + str(cur.fetchone()[0]) + " rows")

        conn.commit()
        print("\nSUCCESS: Loaded " + str(len(files)) + " tables into dw.")
    except Exception:
        conn.rollback()
        raise
    finally:
        duck.close()
        conn.close()

if __name__ == "__main__":
    main()
