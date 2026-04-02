"""Seed the database from Hostel_details.xlsx"""
import sqlite3, pandas as pd, os, sys
from werkzeug.security import generate_password_hash

DB   = os.path.join(os.path.dirname(__file__), 'hostel.db')
XL   = 'C:/Users/hkbka/Downloads/Hostel_details.xlsx'
SQL  = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_conn():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_schema(conn):
    with open(SQL) as f:
        conn.executescript(f.read())
    conn.commit()
    print("Schema initialised")

# ── Floor mapping ────────────────────────────────────────────────────────────
FLOOR_MAP = {
    'Ground Floor': (0, 'Ground Floor'),
    '1st Floor':    (1, '1st Floor'),
    '2nd Floor':    (2, '2nd Floor'),
    '3rd Floor':    (3, '3rd Floor'),
    '4th Floor':    (4, '4th Floor'),
    '5th Floor':    (5, '5th Floor'),
}

# Boys rooms are numbered 1-84 continuously; map to floor-relative
BOYS_FLOOR_RANGES = {
    'Ground Floor': (1, 14),
    '1st Floor':    (15, 28),
    '2nd Floor':    (29, 42),
    '3rd Floor':    (43, 56),
    '4th Floor':    (57, 70),
    '5th Floor':    (71, 84),
}

def boys_room_code(room_num, floor_label):
    floor_num, _ = FLOOR_MAP[floor_label]
    start, _ = BOYS_FLOOR_RANGES[floor_label]
    rel = room_num - start + 1          # 1-based on floor
    return f"B-{floor_num}{rel:02d}"    # e.g. B-001, B-114

def girls_room_code(room_num):
    return f"G-{room_num}"              # already floor-encoded e.g. G-101

def seed_hostels(conn):
    conn.execute("INSERT OR IGNORE INTO hostels(code,name,capacity) VALUES('B','Boys Hostel',180)")
    conn.execute("INSERT OR IGNORE INTO hostels(code,name,capacity) VALUES('G','Girls Hostel',180)")
    conn.commit()
    print("Hostels seeded")

def seed_rooms(conn):
    boys_id  = conn.execute("SELECT id FROM hostels WHERE code='B'").fetchone()['id']
    girls_id = conn.execute("SELECT id FROM hostels WHERE code='G'").fetchone()['id']

    boys = pd.read_excel(XL, sheet_name='Boys ')
    girls = pd.read_excel(XL, sheet_name='Girls')

    boys_rooms = {}
    for _, row in boys.iterrows():
        rn = int(row['Room Name']) if pd.notna(row['Room Name']) else None
        fl = str(row['Floor']).strip() if pd.notna(row['Floor']) else None
        if rn is None or fl is None: continue
        code = boys_room_code(rn, fl)
        if code not in boys_rooms:
            fn, fl_label = FLOOR_MAP[fl]
            conn.execute(
                "INSERT OR IGNORE INTO rooms(hostel_id,room_number,floor_label,floor_num,capacity) VALUES(?,?,?,?,2)",
                (boys_id, code, fl_label, fn)
            )
            boys_rooms[code] = True

    girls_rooms = {}
    for _, row in girls.iterrows():
        rn = int(row['Room Name']) if pd.notna(row['Room Name']) else None
        fl = str(row['Floor']).strip() if pd.notna(row['Floor']) else None
        if rn is None or fl is None: continue
        code = girls_room_code(rn)
        if code not in girls_rooms:
            fn, fl_label = FLOOR_MAP[fl]
            conn.execute(
                "INSERT OR IGNORE INTO rooms(hostel_id,room_number,floor_label,floor_num,capacity) VALUES(?,?,?,?,2)",
                (girls_id, code, fl_label, fn)
            )
            girls_rooms[code] = True

    conn.commit()
    br = conn.execute("SELECT COUNT(*) FROM rooms WHERE hostel_id=?",(boys_id,)).fetchone()[0]
    gr = conn.execute("SELECT COUNT(*) FROM rooms WHERE hostel_id=?",(girls_id,)).fetchone()[0]
    print(f"Rooms seeded — Boys: {br}, Girls: {gr}")

def seed_staff(conn):
    staff = [
        ('gopi',     'gopi1234',     'warden_boys',  'Gopi',     '9843114440', ''),
        ('savithri', 'savithri1234', 'warden_girls', 'Savithri', '9845437414', ''),
        ('arogya',   'arogya1234',   'vendor',       'Aarogya Café', '', ''),
        ('chairman', 'chairman1234', 'chairman',     'Hostel Chairman', '', ''),
    ]
    for uname, pwd, role, name, phone, email in staff:
        ph = generate_password_hash(pwd)
        conn.execute(
            "INSERT OR IGNORE INTO users(username,password_hash,role,full_name,phone,email) VALUES(?,?,?,?,?,?)",
            (uname, ph, role, name, phone, email)
        )
    conn.commit()
    print("Staff accounts seeded")

def seed_students(conn):
    boys_id  = conn.execute("SELECT id FROM hostels WHERE code='B'").fetchone()['id']
    girls_id = conn.execute("SELECT id FROM hostels WHERE code='G'").fetchone()['id']
    boys  = pd.read_excel(XL, sheet_name='Boys ')
    girls = pd.read_excel(XL, sheet_name='Girls')

    def insert_student(row, gender, hostel_id, hostel_code):
        usn  = str(row['Registration ID']).strip() if pd.notna(row['Registration ID']) else None
        name = str(row['Name']).strip() if pd.notna(row['Name']) else 'Unknown'
        if not usn: return
        email = str(row['Email ID']).strip() if pd.notna(row['Email ID']) else ''
        prog  = str(row['Programme']).strip() if pd.notna(row['Programme']) else ''
        phone = str(row['Phone Number']).strip() if pd.notna(row['Phone Number']) else ''
        fp    = str(row["Father's Phone Number"]).strip() if pd.notna(row["Father's Phone Number"]) else ''
        mp    = str(row["Mother's Phone Number"]).strip() if pd.notna(row["Mother's Phone Number"]) else ''
        gp    = str(row["Guardian's Phone Number"]).strip() if pd.notna(row["Guardian's Phone Number"]) else ''
        fe    = str(row["Father's Email ID"]).strip() if pd.notna(row["Father's Email ID"]) else ''
        me    = str(row["Mother's Email ID"]).strip() if pd.notna(row["Mother's Email ID"]) else ''
        allot = str(row['Allotment End Date'])[:10] if pd.notna(row['Allotment End Date']) else ''

        # Create login account: username = USN (lowercase), password = last 4 of USN
        uname = usn.lower()
        pwd   = generate_password_hash(usn[-4:])
        ex = conn.execute("SELECT id FROM users WHERE username=?",(uname,)).fetchone()
        if ex:
            uid = ex['id']
        else:
            conn.execute(
                "INSERT INTO users(username,password_hash,role,full_name,phone,email) VALUES(?,?,?,?,?,?)",
                (uname, pwd, 'student', name, phone, email)
            )
            uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        ex2 = conn.execute("SELECT id FROM students WHERE usn=?",(usn,)).fetchone()
        if ex2:
            sid = ex2['id']
        else:
            conn.execute("""
                INSERT INTO students
                  (user_id,usn,name,gender,programme,email,phone,
                   father_phone,mother_phone,guardian_phone,
                   father_email,mother_email,allotment_end,status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (uid,usn,name,gender,prog,email,phone,fp,mp,gp,fe,me,allot,'active'))
            sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Room allotment
        rn = int(row['Room Name']) if pd.notna(row['Room Name']) else None
        fl = str(row['Floor']).strip() if pd.notna(row['Floor']) else None
        if rn and fl:
            if hostel_code == 'B':
                rcode = boys_room_code(rn, fl)
            else:
                rcode = girls_room_code(rn)
            room = conn.execute(
                "SELECT id FROM rooms WHERE hostel_id=? AND room_number=?",
                (hostel_id, rcode)
            ).fetchone()
            if room:
                existing = conn.execute(
                    "SELECT id FROM room_allotments WHERE student_id=? AND is_current=1",(sid,)
                ).fetchone()
                if not existing:
                    # determine bed number
                    occ = conn.execute(
                        "SELECT COUNT(*) FROM room_allotments WHERE room_id=? AND is_current=1",
                        (room['id'],)
                    ).fetchone()[0]
                    bed = occ + 1
                    conn.execute(
                        "INSERT OR IGNORE INTO room_allotments(student_id,room_id,bed_number) VALUES(?,?,?)",
                        (sid, room['id'], bed)
                    )

    for _, row in boys.iterrows():
        insert_student(row, 'M', boys_id, 'B')
    conn.commit()
    bs = conn.execute("SELECT COUNT(*) FROM students WHERE gender='M'").fetchone()[0]
    print(f"Boys students seeded: {bs}")

    for _, row in girls.iterrows():
        insert_student(row, 'F', girls_id, 'G')
    conn.commit()
    gs = conn.execute("SELECT COUNT(*) FROM students WHERE gender='F'").fetchone()[0]
    print(f"Girls students seeded: {gs}")

def run():
    if os.path.exists(DB):
        os.remove(DB)
        print("Old DB removed")
    conn = get_conn()
    init_schema(conn)
    seed_hostels(conn)
    seed_rooms(conn)
    seed_staff(conn)
    seed_students(conn)
    conn.close()
    print("\nDatabase ready:", DB)
    print("\nDefault login credentials:")
    print("  Boys Warden  : gopi / gopi1234")
    print("  Girls Warden : savithri / savithri1234")
    print("  Vendor       : arogya / arogya1234")
    print("  Chairman     : chairman / chairman1234")
    print("  Students     : <usn_lowercase> / <last_4_of_usn>")

if __name__ == '__main__':
    run()
