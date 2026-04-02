"""
Migration v2 - adds movement_logs, fees, circulars, parent_visits tables
and extends students/users with new columns.
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'hostel.db')

def run():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    # ── New tables ──────────────────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS movement_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id),
        hostel_id  INTEGER NOT NULL REFERENCES hostels(id),
        out_time   TEXT NOT NULL DEFAULT (datetime('now')),
        expected_return TEXT,
        reason     TEXT NOT NULL,
        in_time    TEXT,
        status     TEXT DEFAULT 'out' CHECK(status IN ('out','returned','overdue')),
        recorded_by INTEGER REFERENCES users(id),
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    print("OK movement_logs table ready")

    c.execute("""CREATE TABLE IF NOT EXISTS fees (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id    INTEGER NOT NULL REFERENCES students(id),
        fee_type      TEXT NOT NULL CHECK(fee_type IN ('hostel','mess','other')),
        academic_year TEXT NOT NULL,
        total_amount  REAL NOT NULL,
        paid_amount   REAL DEFAULT 0,
        due_date      TEXT,
        last_payment_date TEXT,
        notes         TEXT,
        created_at    TEXT DEFAULT (datetime('now'))
    )""")
    print("✓ fees table ready")

    c.execute("""CREATE TABLE IF NOT EXISTS circulars (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        title        TEXT NOT NULL,
        content      TEXT NOT NULL,
        published_by INTEGER NOT NULL REFERENCES users(id),
        target       TEXT DEFAULT 'all' CHECK(target IN ('all','boys','girls','students','staff')),
        is_pinned    INTEGER DEFAULT 0,
        is_active    INTEGER DEFAULT 1,
        published_at TEXT DEFAULT (datetime('now'))
    )""")
    print("✓ circulars table ready")

    c.execute("""CREATE TABLE IF NOT EXISTS parent_visits (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id   INTEGER NOT NULL REFERENCES students(id),
        visitor_name TEXT NOT NULL,
        relationship TEXT NOT NULL CHECK(relationship IN ('father','mother','guardian','sibling','other')),
        visit_date   TEXT NOT NULL,
        in_time      TEXT,
        out_time     TEXT,
        purpose      TEXT,
        recorded_by  INTEGER REFERENCES users(id),
        created_at   TEXT DEFAULT (datetime('now'))
    )""")
    print("✓ parent_visits table ready")

    # ── Alter students table ─────────────────────────────────────────────────
    student_cols = [
        ("semester",       "TEXT"),
        ("city",           "TEXT"),
        ("state",          "TEXT"),
        ("blood_group",    "TEXT"),
        ("health_concerns","TEXT"),
        ("mentor_name",    "TEXT"),
        ("mentor_phone",   "TEXT"),
        ("photo_url",      "TEXT"),
    ]
    for col, typ in student_cols:
        try:
            c.execute(f"ALTER TABLE students ADD COLUMN {col} {typ}")
            print(f"  + students.{col} added")
        except Exception as e:
            print(f"  ~ students.{col} already exists ({e})")

    # ── Alter users table ────────────────────────────────────────────────────
    user_cols = [
        ("photo_url", "TEXT"),
        ("address",   "TEXT"),
    ]
    for col, typ in user_cols:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
            print(f"  + users.{col} added")
        except Exception as e:
            print(f"  ~ users.{col} already exists ({e})")

    conn.commit()
    conn.close()
    print("\nMigration v2 complete.")

if __name__ == '__main__':
    run()
