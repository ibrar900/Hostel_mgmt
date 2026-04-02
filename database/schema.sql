PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('student','warden_boys','warden_girls','vendor','chairman')),
    full_name     TEXT NOT NULL,
    phone         TEXT,
    email         TEXT,
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS hostels (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    code     TEXT UNIQUE NOT NULL,   -- 'B' or 'G'
    name     TEXT NOT NULL,
    capacity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id   INTEGER NOT NULL REFERENCES hostels(id),
    room_number TEXT NOT NULL,       -- e.g. B-001, G-101
    floor_label TEXT NOT NULL,       -- 'Ground Floor','1st Floor', etc.
    floor_num   INTEGER NOT NULL,    -- 0,1,2,3,4,5
    capacity    INTEGER DEFAULT 2,
    is_active   INTEGER DEFAULT 1,
    UNIQUE(hostel_id, room_number)
);

CREATE TABLE IF NOT EXISTS students (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER UNIQUE REFERENCES users(id),
    usn             TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    gender          TEXT NOT NULL CHECK(gender IN ('M','F')),
    programme       TEXT,
    email           TEXT,
    phone           TEXT,
    father_phone    TEXT,
    mother_phone    TEXT,
    guardian_phone  TEXT,
    father_email    TEXT,
    mother_email    TEXT,
    food_preference TEXT DEFAULT 'veg' CHECK(food_preference IN ('veg','non-veg')),
    allotment_end   TEXT,
    status          TEXT DEFAULT 'active',
    admission_date  TEXT DEFAULT (date('now')),
    is_active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS room_allotments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    INTEGER NOT NULL REFERENCES students(id),
    room_id       INTEGER NOT NULL REFERENCES rooms(id),
    bed_number    INTEGER DEFAULT 1,
    allotted_date TEXT DEFAULT (date('now')),
    vacated_date  TEXT,
    is_current    INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS attendance_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id    INTEGER NOT NULL REFERENCES hostels(id),
    session_date TEXT NOT NULL,
    marked_by    INTEGER REFERENCES users(id),
    source       TEXT DEFAULT 'manual',
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(hostel_id, session_date)
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES attendance_sessions(id),
    student_id   INTEGER NOT NULL REFERENCES students(id),
    status       TEXT NOT NULL CHECK(status IN ('present','absent','on_leave','out_of_station')),
    marked_at    TEXT DEFAULT (datetime('now')),
    remarks      TEXT,
    UNIQUE(session_id, student_id)
);

CREATE TABLE IF NOT EXISTS permission_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       INTEGER NOT NULL REFERENCES students(id),
    permission_type  TEXT NOT NULL CHECK(permission_type IN ('home_visit','medical','vacation')),
    reason           TEXT NOT NULL,
    from_date        TEXT NOT NULL,
    to_date          TEXT NOT NULL,
    status           TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected','cancelled')),
    reviewed_by      INTEGER REFERENCES users(id),
    review_note      TEXT,
    food_paused      INTEGER DEFAULT 1,
    submitted_at     TEXT DEFAULT (datetime('now')),
    reviewed_at      TEXT,
    actual_return    TEXT
);

CREATE TABLE IF NOT EXISTS weekly_menus (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id     INTEGER NOT NULL REFERENCES hostels(id),
    menu_date     TEXT NOT NULL,
    meal_type     TEXT NOT NULL CHECK(meal_type IN ('breakfast','lunch','dinner')),
    veg_items     TEXT NOT NULL,
    non_veg_items TEXT,
    uploaded_by   INTEGER REFERENCES users(id),
    uploaded_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(hostel_id, menu_date, meal_type)
);

CREATE TABLE IF NOT EXISTS food_complaints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES students(id),
    hostel_id       INTEGER NOT NULL REFERENCES hostels(id),
    meal_date       TEXT NOT NULL,
    meal_type       TEXT CHECK(meal_type IN ('breakfast','lunch','dinner','general')),
    category        TEXT,
    description     TEXT NOT NULL,
    status          TEXT DEFAULT 'open' CHECK(status IN ('open','acknowledged','resolved')),
    vendor_response TEXT,
    warden_note     TEXT,
    submitted_at    TEXT DEFAULT (datetime('now')),
    resolved_at     TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    title      TEXT NOT NULL,
    body       TEXT,
    is_read    INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
