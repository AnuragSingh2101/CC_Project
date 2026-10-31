"""
Database Sync Service: Syncs SQLite records into Docker PostgreSQL
so both databases stay updated and accessible.
"""
import sqlite3
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_sync")

TABLES_IN_ORDER = [
    "organizations",
    "users",
    "inventory_lots",
    "emergency_requests",
    "reservations",
    "donors",
    "donor_appointments",
    "transfer_requests",
    "notifications",
    "audit_logs"
]

def sync_sqlite_to_postgres():
    sqlite_conn = sqlite3.connect("blood_bank.db")
    sqlite_conn.row_factory = sqlite3.Row
    s_cur = sqlite_conn.cursor()

    pg_conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="bloodbank",
        password="changeme",
        dbname="blood_bank_db"
    )
    p_cur = pg_conn.cursor()

    try:
        p_cur.execute("SET session_replication_role = 'replica';")

        for table in TABLES_IN_ORDER:
            # Query PG column types to auto-detect booleans
            p_cur.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}';
            """)
            col_types = {r[0]: r[1] for r in p_cur.fetchall()}
            bool_cols = {col for col, dt in col_types.items() if dt == 'boolean'}

            s_cur.execute(f"SELECT * FROM {table}")
            rows = s_cur.fetchall()
            if not rows:
                continue

            columns = list(rows[0].keys())
            col_names = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))

            p_cur.execute(f"TRUNCATE TABLE {table} CASCADE;")

            row_data = []
            for r in rows:
                vals = []
                for c in columns:
                    val = r[c]
                    if c in bool_cols and val is not None:
                        val = bool(val)
                    vals.append(val)
                row_data.append(tuple(vals))

            insert_sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
            p_cur.executemany(insert_sql, row_data)
            logger.info(f"Synced {len(row_data)} rows into {table} (PostgreSQL)")

        p_cur.execute("SET session_replication_role = 'origin';")
        
        for table in TABLES_IN_ORDER:
            try:
                p_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table};")
            except Exception:
                pass

        pg_conn.commit()
        logger.info("Sync completed successfully!")
    except Exception as e:
        pg_conn.rollback()
        logger.error(f"Sync failed: {e}")
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    sync_sqlite_to_postgres()
