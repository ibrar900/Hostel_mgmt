from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app, send_file
import sqlite3, csv, os
from datetime import date, datetime
from functools import wraps

warden_bp = Blueprint('warden', __name__)

def get_db():
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def warden_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') not in ('warden_boys','warden_girls'):
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@warden_bp.route('/dashboard')
@warden_required
def dashboard():
    db = get_db()
    hid   = session['hostel_id']
    today = date.today().isoformat()
    hostel = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    total_students = db.execute(
        """SELECT COUNT(*) FROM students s
           JOIN room_allotments ra ON ra.student_id=s.id
           JOIN rooms r ON r.id=ra.room_id
           WHERE r.hostel_id=? AND ra.is_current=1 AND s.is_active=1""", (hid,)).fetchone()[0]
    sess = db.execute("SELECT id FROM attendance_sessions WHERE hostel_id=? AND session_date=?", (hid,today)).fetchone()
    present = absent = on_leave = out_of_station = 0
    if sess:
        present       = db.execute("SELECT COUNT(*) FROM attendance_records WHERE session_id=? AND status='present'", (sess['id'],)).fetchone()[0]
        absent        = db.execute("SELECT COUNT(*) FROM attendance_records WHERE session_id=? AND status='absent'", (sess['id'],)).fetchone()[0]
        on_leave      = db.execute("SELECT COUNT(*) FROM attendance_records WHERE session_id=? AND status='on_leave'", (sess['id'],)).fetchone()[0]
        out_of_station= db.execute("SELECT COUNT(*) FROM attendance_records WHERE session_id=? AND status='out_of_station'", (sess['id'],)).fetchone()[0]
    pending_perms = db.execute(
        """SELECT COUNT(*) FROM permission_requests pr
           JOIN students s ON s.id=pr.student_id
           JOIN room_allotments ra ON ra.student_id=s.id
           JOIN rooms r ON r.id=ra.room_id
           WHERE r.hostel_id=? AND pr.status='pending'""", (hid,)).fetchone()[0]
    open_complaints = db.execute(
        "SELECT COUNT(*) FROM food_complaints WHERE hostel_id=? AND status='open'", (hid,)).fetchone()[0]
    total_rooms = db.execute("SELECT COUNT(*) FROM rooms WHERE hostel_id=?", (hid,)).fetchone()[0]
    occupied_rooms = db.execute(
        """SELECT COUNT(DISTINCT ra.room_id) FROM room_allotments ra
           JOIN rooms r ON r.id=ra.room_id
           WHERE r.hostel_id=? AND ra.is_current=1""", (hid,)).fetchone()[0]
    recent_perms = db.execute(
        """SELECT pr.*, s.name, s.usn FROM permission_requests pr
           JOIN students s ON s.id=pr.student_id
           JOIN room_allotments ra ON ra.student_id=s.id
           JOIN rooms r ON r.id=ra.room_id
           WHERE r.hostel_id=? AND pr.status='pending'
           ORDER BY pr.submitted_at DESC LIMIT 5""", (hid,)).fetchall()
    recent_complaints = db.execute(
        """SELECT fc.*, s.name FROM food_complaints fc
           JOIN students s ON s.id=fc.student_id
           WHERE fc.hostel_id=? AND fc.status='open'
           ORDER BY fc.submitted_at DESC LIMIT 5""", (hid,)).fetchall()
    db.close()
    return render_template('warden/dashboard.html',
        hostel=hostel, today=today,
        total_students=total_students, present=present, absent=absent,
        on_leave=on_leave, out_of_station=out_of_station,
        pending_perms=pending_perms, open_complaints=open_complaints,
        total_rooms=total_rooms, occupied_rooms=occupied_rooms,
        recent_perms=recent_perms, recent_complaints=recent_complaints,
        attendance_done=(sess is not None))

@warden_bp.route('/students')
@warden_required
def students():
    db  = get_db()
    hid = session['hostel_id']
    q   = request.args.get('q','').strip()
    page= int(request.args.get('page',1))
    per_page = 20
    base_q = """SELECT s.*, ra.room_id, r.room_number
                FROM students s
                JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
                JOIN rooms r ON r.id=ra.room_id
                WHERE r.hostel_id=? AND s.is_active=1"""
    params = [hid]
    if q:
        base_q += " AND (s.name LIKE ? OR s.usn LIKE ? OR r.room_number LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    base_q += " ORDER BY r.room_number, s.name"
    all_students = db.execute(base_q, params).fetchall()
    total = len(all_students)
    total_pages = (total + per_page - 1) // per_page
    students_page = all_students[(page-1)*per_page : page*per_page]
    db.close()
    return render_template('warden/students.html',
        students=students_page, total=total, total_count=total,
        total_pages=total_pages, page=page, per_page=per_page, q=q)

@warden_bp.route('/students/add', methods=['GET','POST'])
@warden_required
def add_student():
    db  = get_db()
    hid = session['hostel_id']
    hostel = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    rooms  = db.execute(
        """SELECT r.*, (SELECT COUNT(*) FROM room_allotments ra WHERE ra.room_id=r.id AND ra.is_current=1) as occ
           FROM rooms r WHERE r.hostel_id=? AND r.is_active=1
           ORDER BY r.floor_num, r.room_number""", (hid,)).fetchall()
    if request.method == 'POST':
        usn      = request.form.get('usn','').strip().upper()
        name     = request.form.get('name','').strip()
        prog     = request.form.get('programme','').strip()
        email    = request.form.get('email','').strip()
        phone    = request.form.get('phone','').strip()
        fp       = request.form.get('father_phone','').strip()
        mp       = request.form.get('mother_phone','').strip()
        room_id  = request.form.get('room_id','')
        food_pref= request.form.get('food_preference','veg')
        gender   = hostel['code'] == 'G' and 'F' or 'M'
        from werkzeug.security import generate_password_hash
        uname = usn.lower()
        pwd   = generate_password_hash(usn[-4:])
        try:
            db.execute("INSERT INTO users(username,password_hash,role,full_name,phone,email) VALUES(?,?,?,?,?,?)",
                       (uname, pwd, 'student', name, phone, email))
            uid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("""INSERT INTO students(user_id,usn,name,gender,programme,email,phone,
                          father_phone,mother_phone,food_preference)
                          VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (uid,usn,name,gender,prog,email,phone,fp,mp,food_pref))
            sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            if room_id:
                occ = db.execute("SELECT COUNT(*) FROM room_allotments WHERE room_id=? AND is_current=1",(room_id,)).fetchone()[0]
                db.execute("INSERT INTO room_allotments(student_id,room_id,bed_number) VALUES(?,?,?)",
                           (sid,room_id,occ+1))
            db.commit()
            flash(f'Student {name} added successfully. Login: {uname} / {usn[-4:]}', 'success')
            return redirect(url_for('warden.students'))
        except Exception as e:
            flash(f'Error: {e}', 'error')
    db.close()
    return render_template('warden/add_student.html', hostel=hostel, rooms=rooms)

@warden_bp.route('/rooms')
@warden_required
def rooms():
    db  = get_db()
    hid = session['hostel_id']
    hostel = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()

    # floor_num → template key mapping
    floor_key_map = {0:'ground', 1:'1st', 2:'2nd', 3:'3rd', 4:'4th', 5:'5th'}

    raw_floors = db.execute(
        "SELECT DISTINCT floor_num, floor_label FROM rooms WHERE hostel_id=? ORDER BY floor_num", (hid,)
    ).fetchall()

    rooms_by_floor = {}
    all_room_stats = []

    for fl in raw_floors:
        raw_rooms = db.execute("""
            SELECT r.id, r.room_number, r.capacity, r.floor_num
            FROM rooms r
            WHERE r.hostel_id=? AND r.floor_num=?
            ORDER BY r.room_number
        """, (hid, fl['floor_num'])).fetchall()

        floor_rooms = []
        for r in raw_rooms:
            occupants_rows = db.execute("""
                SELECT s.name FROM students s
                JOIN room_allotments ra ON ra.student_id=s.id
                WHERE ra.room_id=? AND ra.is_current=1
            """, (r['id'],)).fetchall()
            occupied = len(occupants_rows)
            floor_rooms.append({
                'id':       r['id'],
                'number':   r['room_number'],
                'capacity': r['capacity'],
                'occupied': occupied,
                'occupants': occupants_rows,
            })
            all_room_stats.append({'occupied': occupied, 'capacity': r['capacity']})

        key = floor_key_map.get(fl['floor_num'], str(fl['floor_num']))
        rooms_by_floor[key] = floor_rooms

    total_rooms   = len(all_room_stats)
    full_rooms    = sum(1 for r in all_room_stats if r['occupied'] >= r['capacity'])
    partial_rooms = sum(1 for r in all_room_stats if 0 < r['occupied'] < r['capacity'])
    empty_rooms   = sum(1 for r in all_room_stats if r['occupied'] == 0)
    db.close()
    return render_template('warden/rooms.html', hostel=hostel,
        rooms_by_floor=rooms_by_floor,
        total_rooms=total_rooms, full_rooms=full_rooms,
        partial_rooms=partial_rooms, empty_rooms=empty_rooms)

@warden_bp.route('/attendance', methods=['GET','POST'])
@warden_required
def attendance():
    db   = get_db()
    hid  = session['hostel_id']
    today= date.today().isoformat()
    sel_date = request.args.get('date', today)
    hostel   = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()

    if request.method == 'POST':
        # accept both 'date' (from template) and 'att_date' (legacy)
        att_date = request.form.get('date') or request.form.get('att_date', today)
        source   = request.form.get('source','manual')
        sess = db.execute("SELECT id FROM attendance_sessions WHERE hostel_id=? AND session_date=?",(hid,att_date)).fetchone()
        if not sess:
            db.execute("INSERT INTO attendance_sessions(hostel_id,session_date,marked_by,source) VALUES(?,?,?,?)",
                       (hid,att_date,session['user_id'],source))
            db.commit()
            sess = db.execute("SELECT id FROM attendance_sessions WHERE hostel_id=? AND session_date=?",(hid,att_date)).fetchone()
        sid_list = request.form.getlist('student_ids')
        statuses = request.form.to_dict()
        for stu_id in sid_list:
            status = statuses.get(f'status_{stu_id}','absent')
            db.execute("""INSERT INTO attendance_records(session_id,student_id,status,marked_by)
                          VALUES(?,?,?,?) ON CONFLICT(session_id,student_id) DO UPDATE SET status=excluded.status""",
                       (sess['id'], int(stu_id), status, session['user_id']))
        db.commit()
        flash(f'Attendance saved for {att_date}', 'success')
        return redirect(url_for('warden.attendance', date=att_date))

    students = db.execute("""
        SELECT s.id, s.name, s.usn, r.room_number, s.food_preference
        FROM students s
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND s.is_active=1
        ORDER BY r.room_number, s.name
    """, (hid,)).fetchall()

    sess = db.execute("SELECT id FROM attendance_sessions WHERE hostel_id=? AND session_date=?",(hid,sel_date)).fetchone()
    existing = {}
    if sess:
        recs = db.execute("SELECT student_id,status FROM attendance_records WHERE session_id=?",(sess['id'],)).fetchall()
        existing = {r['student_id']: r['status'] for r in recs}

    # auto-mark out_of_station for approved permissions
    approved_perm = db.execute("""
        SELECT pr.student_id FROM permission_requests pr
        JOIN students s ON s.id=pr.student_id
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND pr.status='approved'
          AND pr.from_date<=? AND pr.to_date>=?
    """, (hid, sel_date, sel_date)).fetchall()
    auto_out = {r['student_id'] for r in approved_perm}

    db.close()
    already_marked = sess is not None
    return render_template('warden/attendance.html',
        hostel=hostel, students=students,
        sel_date=sel_date, selected_date=sel_date,
        existing=existing, attendance=existing,
        auto_out=auto_out, today=today,
        already_marked=already_marked)

@warden_bp.route('/attendance/save', methods=['POST'])
@warden_required
def save_attendance():
    """Alias route used by the attendance form template."""
    return attendance()

@warden_bp.route('/attendance/upload', methods=['POST'])
@warden_required
def upload_biometric():
    db  = get_db()
    hid = session['hostel_id']
    f   = request.files.get('bio_file') or request.files.get('csv_file')
    att_date = request.form.get('att_date', date.today().isoformat())
    if not f:
        flash('No file uploaded', 'error')
        return redirect(url_for('warden.attendance'))
    path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'biometric', f.filename)
    f.save(path)
    try:
        import csv as csvmod
        present_usns = set()
        with open(path, newline='', encoding='utf-8-sig') as cf:
            reader = csv.DictReader(cf)
            for row in reader:
                usn_key = next((k for k in row if 'usn' in k.lower() or 'id' in k.lower()), None)
                if usn_key:
                    present_usns.add(row[usn_key].strip().upper())
        sess = db.execute("SELECT id FROM attendance_sessions WHERE hostel_id=? AND session_date=?",(hid,att_date)).fetchone()
        if not sess:
            db.execute("INSERT INTO attendance_sessions(hostel_id,session_date,marked_by,source) VALUES(?,?,?,?)",
                       (hid,att_date,session['user_id'],'biometric'))
            db.commit()
            sess = db.execute("SELECT id FROM attendance_sessions WHERE hostel_id=? AND session_date=?",(hid,att_date)).fetchone()
        students = db.execute("""SELECT s.id,s.usn FROM students s
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id WHERE r.hostel_id=? AND s.is_active=1""",(hid,)).fetchall()
        count = 0
        for stu in students:
            status = 'present' if stu['usn'] in present_usns else 'absent'
            db.execute("""INSERT INTO attendance_records(session_id,student_id,status,marked_by)
                VALUES(?,?,?,?) ON CONFLICT(session_id,student_id) DO UPDATE SET status=excluded.status""",
                (sess['id'],stu['id'],status,session['user_id']))
            count += 1
        db.commit()
        flash(f'Biometric processed: {len(present_usns)} present, {count-len(present_usns)} absent', 'success')
    except Exception as e:
        flash(f'Error processing file: {e}', 'error')
    db.close()
    return redirect(url_for('warden.attendance', date=att_date))

@warden_bp.route('/permissions')
@warden_required
def permissions():
    db   = get_db()
    hid  = session['hostel_id']
    status_filter = request.args.get('status','pending')
    perms = db.execute("""
        SELECT pr.*,
               s.name as student_name, s.usn, s.phone as student_phone,
               s.father_phone, s.mother_phone, s.guardian_phone,
               pr.permission_type as type,
               pr.review_note as warden_note,
               r.room_number
        FROM permission_requests pr
        JOIN students s ON s.id=pr.student_id
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND pr.status=?
        ORDER BY pr.submitted_at DESC
    """, (hid, status_filter)).fetchall()
    pending_count = db.execute("""SELECT COUNT(*) FROM permission_requests pr
        JOIN students s ON s.id=pr.student_id
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND pr.status='pending'""", (hid,)).fetchone()[0]
    db.close()
    return render_template('warden/permissions.html',
        perms=perms, permissions=perms,
        status_filter=status_filter, pending_count=pending_count)

@warden_bp.route('/permissions/<int:pid>/action', methods=['POST'])
@warden_required
def permission_action(pid):
    db     = get_db()
    action = request.form.get('action')
    note   = request.form.get('note','')
    now    = datetime.now().isoformat()
    if action in ('approved','rejected'):
        db.execute("""UPDATE permission_requests SET status=?,reviewed_by=?,review_note=?,reviewed_at=?
                      WHERE id=?""", (action, session['user_id'], note, now, pid))
        db.commit()
        flash(f'Permission {action}', 'success')
    db.close()
    return redirect(url_for('warden.permissions'))

@warden_bp.route('/permissions/approve', methods=['POST'])
@warden_required
def approve_permission():
    pid  = request.form.get('permission_id', type=int)
    note = request.form.get('note','')
    now  = datetime.now().isoformat()
    db   = get_db()
    db.execute("""UPDATE permission_requests SET status='approved',reviewed_by=?,review_note=?,reviewed_at=?
                  WHERE id=?""", (session['user_id'], note, now, pid))
    db.commit()
    db.close()
    flash('Permission approved', 'success')
    redirect_to = request.form.get('redirect_to', url_for('warden.permissions'))
    return redirect(redirect_to)

@warden_bp.route('/permissions/reject', methods=['POST'])
@warden_required
def reject_permission():
    pid  = request.form.get('permission_id', type=int)
    note = request.form.get('note','')
    now  = datetime.now().isoformat()
    db   = get_db()
    db.execute("""UPDATE permission_requests SET status='rejected',reviewed_by=?,review_note=?,reviewed_at=?
                  WHERE id=?""", (session['user_id'], note, now, pid))
    db.commit()
    db.close()
    flash('Permission rejected', 'info')
    redirect_to = request.form.get('redirect_to', url_for('warden.permissions'))
    return redirect(redirect_to)

@warden_bp.route('/complaints')
@warden_required
def complaints():
    db  = get_db()
    hid = session['hostel_id']
    status_f = request.args.get('status','open')
    comps = db.execute("""
        SELECT fc.*, s.name, s.usn, r.room_number
        FROM food_complaints fc
        JOIN students s ON s.id=fc.student_id
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE fc.hostel_id=? AND fc.status=?
        ORDER BY fc.submitted_at DESC
    """, (hid, status_f)).fetchall()
    open_count = db.execute(
        "SELECT COUNT(*) FROM food_complaints WHERE hostel_id=? AND status='open'", (hid,)).fetchone()[0]
    db.close()
    return render_template('warden/complaints.html',
        complaints=comps, status_filter=status_f, open_count=open_count)

@warden_bp.route('/complaints/<int:cid>/note', methods=['POST'])
@warden_required
def complaint_note(cid):
    db   = get_db()
    note = request.form.get('note','')
    db.execute("UPDATE food_complaints SET warden_note=? WHERE id=?", (note, cid))
    db.commit()
    db.close()
    flash('Note saved', 'success')
    return redirect(url_for('warden.complaints'))

@warden_bp.route('/complaints/note', methods=['POST'])
@warden_required
def add_complaint_note():
    """Alias used by complaints template (posts complaint_id as form field)."""
    cid  = request.form.get('complaint_id', type=int)
    note = request.form.get('note','')
    db   = get_db()
    db.execute("UPDATE food_complaints SET warden_note=? WHERE id=?", (note, cid))
    db.commit()
    db.close()
    flash('Note saved', 'success')
    return redirect(url_for('warden.complaints'))

@warden_bp.route('/students/<int:student_id>')
@warden_required
def student_detail(student_id):
    db  = get_db()
    hid = session['hostel_id']
    student = db.execute("""
        SELECT s.*, r.room_number, r.floor_label, h.name as hostel_name
        FROM students s
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        JOIN hostels h ON h.id=r.hostel_id
        WHERE s.id=? AND r.hostel_id=?
    """, (student_id, hid)).fetchone()
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('warden.students'))
    perms = db.execute("SELECT * FROM permission_requests WHERE student_id=? ORDER BY submitted_at DESC LIMIT 10", (student_id,)).fetchall()
    att = db.execute("""
        SELECT SUM(CASE WHEN ar.status='present' THEN 1 ELSE 0 END) as present,
               COUNT(*) as total
        FROM attendance_records ar WHERE ar.student_id=?
    """, (student_id,)).fetchone()
    fees = db.execute("SELECT * FROM fees WHERE student_id=? ORDER BY created_at DESC", (student_id,)).fetchall()
    visits = db.execute("SELECT * FROM parent_visits WHERE student_id=? ORDER BY visit_date DESC LIMIT 10", (student_id,)).fetchall()
    db.close()
    return render_template('warden/student_detail.html', student=student, perms=perms, att=att, fees=fees, visits=visits)

@warden_bp.route('/students/<int:student_id>/edit', methods=['GET','POST'])
@warden_required
def edit_student(student_id):
    db  = get_db()
    hid = session['hostel_id']
    student = db.execute("""
        SELECT s.*, r.room_number, ra.room_id
        FROM students s
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE s.id=? AND r.hostel_id=?
    """, (student_id, hid)).fetchone()
    if not student:
        flash('Student not found', 'error')
        return redirect(url_for('warden.students'))
    if request.method == 'POST':
        name     = request.form.get('name','').strip()
        email    = request.form.get('email','').strip()
        phone    = request.form.get('phone','').strip()
        fp       = request.form.get('father_phone','').strip()
        mp       = request.form.get('mother_phone','').strip()
        food     = request.form.get('food_preference','veg')
        semester = request.form.get('semester','').strip() or None
        city     = request.form.get('city','').strip() or None
        state    = request.form.get('state','').strip() or None
        blood    = request.form.get('blood_group','').strip() or None
        health   = request.form.get('health_concerns','').strip() or None
        mname    = request.form.get('mentor_name','').strip() or None
        mphone   = request.form.get('mentor_phone','').strip() or None
        db.execute("""UPDATE students SET name=?,email=?,phone=?,father_phone=?,mother_phone=?,
                      food_preference=?,semester=?,city=?,state=?,blood_group=?,health_concerns=?,
                      mentor_name=?,mentor_phone=?
                      WHERE id=?""",
                   (name,email,phone,fp,mp,food,semester,city,state,blood,health,mname,mphone,student_id))
        db.commit()
        flash('Student updated', 'success')
        db.close()
        return redirect(url_for('warden.students'))
    rooms = db.execute("SELECT * FROM rooms WHERE hostel_id=? AND is_active=1 ORDER BY room_number", (hid,)).fetchall()
    db.close()
    return render_template('warden/edit_student.html', student=student, rooms=rooms)

@warden_bp.route('/menu')
@warden_required
def menu():
    db  = get_db()
    hid = session['hostel_id']
    sel_date = request.args.get('date', date.today().isoformat())
    rows = db.execute(
        "SELECT * FROM weekly_menus WHERE hostel_id=? AND menu_date=? ORDER BY meal_type",
        (hid, sel_date)).fetchall()
    # Pivot list of rows into a single dict: breakfast_veg, lunch_veg, dinner_veg, etc.
    menu = {}
    for r in rows:
        mt = r['meal_type']
        menu[f'{mt}_veg']    = r['veg_items']
        menu[f'{mt}_nonveg'] = r['non_veg_items'] or ''
    menu = menu if menu else None
    today = date.today().isoformat()
    db.close()
    return render_template('warden/menu.html',
        menu=menu, menus=rows,
        sel_date=sel_date, selected_date=sel_date, today=today)

@warden_bp.route('/reports')
@warden_required
def reports():
    db    = get_db()
    hid   = session['hostel_id']
    hostel= db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    rtype = request.args.get('type','attendance')
    from_d= request.args.get('from', date.today().replace(day=1).isoformat())
    to_d  = request.args.get('to', date.today().isoformat())
    fmt   = request.args.get('fmt','html')
    data  = []

    status_f  = request.args.get('status', 'all')
    cat_filter= request.args.get('category', 'all')

    if rtype == 'attendance':
        data = db.execute("""
            SELECT s.name, s.usn, r.room_number,
              SUM(CASE WHEN ar.status='present' THEN 1 ELSE 0 END) as present_days,
              SUM(CASE WHEN ar.status='absent'  THEN 1 ELSE 0 END) as absent_days,
              SUM(CASE WHEN ar.status='on_leave' THEN 1 ELSE 0 END) as leave_days,
              SUM(CASE WHEN ar.status='out_of_station' THEN 1 ELSE 0 END) as oos_days,
              COUNT(ar.id) as total_days
            FROM students s
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id
            LEFT JOIN attendance_records ar ON ar.student_id=s.id
            LEFT JOIN attendance_sessions asn ON asn.id=ar.session_id
              AND asn.session_date BETWEEN ? AND ?
            WHERE r.hostel_id=? AND s.is_active=1
            GROUP BY s.id ORDER BY r.room_number, s.name
        """, (from_d, to_d, hid)).fetchall()

    elif rtype == 'permissions':
        qry = """SELECT s.name, s.usn, r.room_number, pr.permission_type,
                        pr.from_date, pr.to_date, pr.reason, pr.status, pr.submitted_at
                 FROM permission_requests pr
                 JOIN students s ON s.id=pr.student_id
                 JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
                 JOIN rooms r ON r.id=ra.room_id
                 WHERE r.hostel_id=? AND pr.submitted_at BETWEEN ? AND ?"""
        params = [hid, from_d, to_d]
        if status_f != 'all': qry += " AND pr.status=?"; params.append(status_f)
        qry += " ORDER BY pr.submitted_at DESC"
        data = db.execute(qry, params).fetchall()

    elif rtype == 'occupancy':
        data = db.execute("""
            SELECT r.room_number, r.floor_label, r.capacity,
              COUNT(ra.id) as occupied,
              GROUP_CONCAT(s.name,' / ') as students,
              GROUP_CONCAT(s.usn,' / ') as usns
            FROM rooms r
            LEFT JOIN room_allotments ra ON ra.room_id=r.id AND ra.is_current=1
            LEFT JOIN students s ON s.id=ra.student_id
            WHERE r.hostel_id=?
            GROUP BY r.id ORDER BY r.floor_num, r.room_number
        """, (hid,)).fetchall()

    elif rtype == 'fees':
        status_clause = ""
        if status_f == 'due':     status_clause = " HAVING (COALESCE(SUM(f.total_amount),0)-COALESCE(SUM(f.paid_amount),0))>0"
        elif status_f == 'paid':  status_clause = " HAVING COALESCE(SUM(f.total_amount),0)>0 AND COALESCE(SUM(f.paid_amount),0)>=COALESCE(SUM(f.total_amount),0)"
        elif status_f == 'partial': status_clause = " HAVING COALESCE(SUM(f.paid_amount),0)>0 AND (COALESCE(SUM(f.total_amount),0)-COALESCE(SUM(f.paid_amount),0))>0"
        data = db.execute(f"""
            SELECT s.name, s.usn, r.room_number,
                   COALESCE(SUM(f.total_amount),0) as total_amount,
                   COALESCE(SUM(f.paid_amount),0)  as paid_amount,
                   COALESCE(SUM(f.total_amount),0)-COALESCE(SUM(f.paid_amount),0) as due_amount
            FROM students s
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id
            LEFT JOIN fees f ON f.student_id=s.id
            WHERE r.hostel_id=? AND s.is_active=1
            GROUP BY s.id {status_clause}
            ORDER BY r.room_number, s.name
        """, (hid,)).fetchall()

    elif rtype == 'complaints':
        qry = """SELECT s.name, s.usn, r.room_number, fc.meal_date, fc.category,
                        fc.description, fc.status, fc.submitted_at
                 FROM food_complaints fc
                 JOIN students s ON s.id=fc.student_id
                 JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
                 JOIN rooms r ON r.id=ra.room_id
                 WHERE fc.hostel_id=? AND fc.submitted_at BETWEEN ? AND ?"""
        params = [hid, from_d, to_d]
        if cat_filter != 'all': qry += " AND fc.category=?"; params.append(cat_filter)
        if status_f   != 'all': qry += " AND fc.status=?";   params.append(status_f)
        qry += " ORDER BY fc.submitted_at DESC"
        data = db.execute(qry, params).fetchall()

    if fmt == 'csv':
        from io import StringIO
        si  = StringIO()
        cw  = csv.writer(si)
        if data:
            cw.writerow(data[0].keys())
            for row in data: cw.writerow(list(row))
        si.seek(0)
        from flask import Response
        db.close()
        return Response(si, mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename={rtype}_{from_d}_{to_d}.csv'})

    db.close()
    return render_template('warden/reports.html',
        hostel=hostel, rtype=rtype,
        from_d=from_d, to_d=to_d,
        data=data, fmt=fmt,
        status_f=status_f, cat_filter=cat_filter)

# ─────────────────────────────────────────────────────────────
# FULL REPORT
# ─────────────────────────────────────────────────────────────
@warden_bp.route('/reports/full')
@warden_required
def full_report():
    db    = get_db()
    hid   = session['hostel_id']
    hostel= db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    students = db.execute("""
        SELECT s.*, r.room_number, r.floor_label,
               COALESCE(f.total_amount,0) as fee_total,
               COALESCE(f.paid_amount,0)  as fee_paid
        FROM students s
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        LEFT JOIN fees f ON f.student_id=s.id
        WHERE r.hostel_id=? AND s.is_active=1
        GROUP BY s.id ORDER BY r.room_number, s.name
    """, (hid,)).fetchall()
    total_s = len(students)
    veg_c   = sum(1 for s in students if s['food_preference']=='veg')
    db.close()
    return render_template('warden/full_report.html',
        hostel=hostel, students=students,
        total_students=total_s, veg_count=veg_c, nv_count=total_s-veg_c)

# ─────────────────────────────────────────────────────────────
# MOVEMENT LOG
# ─────────────────────────────────────────────────────────────
@warden_bp.route('/movement')
@warden_required
def movement():
    db  = get_db()
    hid = session['hostel_id']
    hostel = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    is_girls = (hostel['code'] == 'G')
    curfew   = '19:30' if is_girls else '21:30'
    now_str  = datetime.now().strftime('%H:%M')

    outside = db.execute("""
        SELECT ml.*, s.name, s.usn, r.room_number
        FROM movement_logs ml
        JOIN students s ON s.id=ml.student_id
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE ml.hostel_id=? AND ml.status='out'
        ORDER BY ml.out_time DESC
    """, (hid,)).fetchall()

    on_leave = db.execute("""
        SELECT s.name, s.usn, r.room_number, pr.from_date, pr.to_date, pr.reason
        FROM permission_requests pr
        JOIN students s ON s.id=pr.student_id
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND pr.status='approved'
          AND pr.from_date <= date('now') AND pr.to_date >= date('now')
    """, (hid,)).fetchall()

    all_students = db.execute("""
        SELECT s.id, s.name, s.usn, r.room_number
        FROM students s
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND s.is_active=1
        ORDER BY r.room_number, s.name
    """, (hid,)).fetchall()

    outside_ids = {row['student_id'] for row in outside}
    in_hostel = [s for s in all_students if s['id'] not in outside_ids]

    db.close()
    return render_template('warden/movement.html',
        hostel=hostel, curfew=curfew, now_str=now_str,
        outside=outside, on_leave=on_leave,
        in_hostel=in_hostel, is_girls=is_girls)

@warden_bp.route('/movement/return', methods=['POST'])
@warden_required
def movement_return():
    db  = get_db()
    hid = session['hostel_id']
    sid = request.form.get('student_id', type=int)
    now = datetime.now().isoformat(timespec='seconds')
    db.execute("""UPDATE movement_logs SET in_time=?, status='returned'
                  WHERE student_id=? AND hostel_id=? AND status='out'""",
               (now, sid, hid))
    db.commit()
    db.close()
    flash('Student marked as returned.', 'success')
    return redirect(url_for('warden.movement'))

# ─────────────────────────────────────────────────────────────
# FEES
# ─────────────────────────────────────────────────────────────
@warden_bp.route('/fees')
@warden_required
def fees():
    db  = get_db()
    hid = session['hostel_id']
    students = db.execute("""
        SELECT s.id, s.name, s.usn, r.room_number,
               COALESCE(SUM(f.total_amount),0)  as total_amount,
               COALESCE(SUM(f.paid_amount),0)   as paid_amount
        FROM students s
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        LEFT JOIN fees f ON f.student_id=s.id
        WHERE r.hostel_id=? AND s.is_active=1
        GROUP BY s.id ORDER BY r.room_number, s.name
    """, (hid,)).fetchall()
    total_dues      = sum(max(s['total_amount']-s['paid_amount'],0) for s in students)
    total_collected = sum(s['paid_amount'] for s in students)
    db.close()
    return render_template('warden/fees.html',
        students=students, total_dues=total_dues, total_collected=total_collected)

@warden_bp.route('/fees/update', methods=['POST'])
@warden_required
def fees_update():
    db  = get_db()
    sid        = request.form.get('student_id', type=int)
    fee_type   = request.form.get('fee_type','hostel')
    acad_year  = request.form.get('academic_year','').strip()
    total_amt  = request.form.get('total_amount', type=float, default=0)
    paid_amt   = request.form.get('paid_amount',  type=float, default=0)
    due_date   = request.form.get('due_date','').strip() or None
    notes      = request.form.get('notes','').strip() or None
    now        = datetime.now().isoformat(timespec='seconds')
    existing   = db.execute("SELECT id FROM fees WHERE student_id=? AND fee_type=? AND academic_year=?",
                            (sid, fee_type, acad_year)).fetchone()
    if existing:
        db.execute("""UPDATE fees SET total_amount=?,paid_amount=?,due_date=?,
                      last_payment_date=?,notes=? WHERE id=?""",
                   (total_amt, paid_amt, due_date, now, notes, existing['id']))
    else:
        db.execute("""INSERT INTO fees(student_id,fee_type,academic_year,total_amount,
                      paid_amount,due_date,last_payment_date,notes,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?)""",
                   (sid, fee_type, acad_year, total_amt, paid_amt, due_date, now, notes, now))
    db.commit()
    db.close()
    flash('Fee record updated.', 'success')
    return redirect(url_for('warden.fees'))

# ─────────────────────────────────────────────────────────────
# CIRCULARS
# ─────────────────────────────────────────────────────────────
@warden_bp.route('/circulars', methods=['GET','POST'])
@warden_required
def circulars():
    db  = get_db()
    if request.method == 'POST':
        title   = request.form.get('title','').strip()
        content = request.form.get('content','').strip()
        target  = request.form.get('target','all')
        pinned  = 1 if request.form.get('is_pinned') else 0
        now     = datetime.now().isoformat(timespec='seconds')
        if title and content:
            db.execute("""INSERT INTO circulars(title,content,published_by,target,is_pinned,is_active,published_at)
                          VALUES(?,?,?,?,?,1,?)""",
                       (title, content, session['user_id'], target, pinned, now))
            db.commit()
            flash('Circular published.', 'success')
        else:
            flash('Title and content are required.', 'error')
        db.close()
        return redirect(url_for('warden.circulars'))

    all_circulars = db.execute("""SELECT c.*, u.full_name as author
                                   FROM circulars c JOIN users u ON u.id=c.published_by
                                   ORDER BY c.is_pinned DESC, c.published_at DESC""").fetchall()
    db.close()
    return render_template('warden/circulars.html', circulars=all_circulars)

@warden_bp.route('/circulars/<int:cid>/delete', methods=['POST'])
@warden_required
def delete_circular(cid):
    db = get_db()
    db.execute("UPDATE circulars SET is_active=0 WHERE id=?", (cid,))
    db.commit()
    db.close()
    flash('Circular deactivated.', 'info')
    return redirect(url_for('warden.circulars'))

# ─────────────────────────────────────────────────────────────
# PARENT VISITS
# ─────────────────────────────────────────────────────────────
@warden_bp.route('/visits', methods=['GET','POST'])
@warden_required
def visits():
    db  = get_db()
    hid = session['hostel_id']
    q   = request.args.get('q','').strip()
    today = date.today().isoformat()

    if request.method == 'POST':
        return redirect(url_for('warden.visits'))

    today_visits = db.execute("""
        SELECT pv.*, s.name as student_name, s.usn, r.room_number
        FROM parent_visits pv
        JOIN students s ON s.id=pv.student_id
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND pv.visit_date=?
        ORDER BY pv.created_at DESC
    """, (hid, today)).fetchall()

    search_results = []
    if q:
        search_results = db.execute("""
            SELECT pv.*, s.name as student_name, s.usn, r.room_number
            FROM parent_visits pv
            JOIN students s ON s.id=pv.student_id
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id
            WHERE r.hostel_id=? AND (s.name LIKE ? OR s.usn LIKE ?)
            ORDER BY pv.visit_date DESC LIMIT 30
        """, (hid, f'%{q}%', f'%{q}%')).fetchall()

    students = db.execute("""
        SELECT s.id, s.name, s.usn, r.room_number
        FROM students s
        JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        JOIN rooms r ON r.id=ra.room_id
        WHERE r.hostel_id=? AND s.is_active=1
        ORDER BY s.name
    """, (hid,)).fetchall()

    db.close()
    return render_template('warden/visits.html',
        today_visits=today_visits, students=students,
        search_results=search_results, q=q, today=today)

@warden_bp.route('/visits/add', methods=['POST'])
@warden_required
def add_visit():
    db  = get_db()
    sid      = request.form.get('student_id', type=int)
    vname    = request.form.get('visitor_name','').strip()
    rel      = request.form.get('relationship','other')
    vdate    = request.form.get('visit_date', date.today().isoformat())
    in_t     = request.form.get('in_time','').strip() or None
    out_t    = request.form.get('out_time','').strip() or None
    purpose  = request.form.get('purpose','').strip() or None
    now      = datetime.now().isoformat(timespec='seconds')
    if sid and vname:
        db.execute("""INSERT INTO parent_visits(student_id,visitor_name,relationship,visit_date,
                      in_time,out_time,purpose,recorded_by,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?)""",
                   (sid, vname, rel, vdate, in_t, out_t, purpose, session['user_id'], now))
        db.commit()
        flash('Visit recorded.', 'success')
    else:
        flash('Student and visitor name are required.', 'error')
    db.close()
    return redirect(url_for('warden.visits'))

# ─────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────
@warden_bp.route('/protocols')
@warden_required
def protocols():
    db      = get_db()
    hid     = session['hostel_id']
    hostel  = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    wardens = db.execute("SELECT full_name, phone, role FROM users WHERE role IN ('warden_boys','warden_girls') AND is_active=1").fetchall()
    chairman= db.execute("SELECT full_name, phone FROM users WHERE role='chairman' AND is_active=1 LIMIT 1").fetchone()
    db.close()
    return render_template('shared/protocols.html',
        hostel=hostel, wardens=wardens, chairman=chairman,
        is_girls=(hostel['code']=='G'))

# ─────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────
@warden_bp.route('/profile', methods=['GET','POST'])
@warden_required
def profile():
    db  = get_db()
    uid = session['user_id']
    user = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if request.method == 'POST':
        full_name = request.form.get('full_name','').strip()
        phone     = request.form.get('phone','').strip()
        email     = request.form.get('email','').strip()
        address   = request.form.get('address','').strip()
        photo     = request.files.get('photo')
        photo_url = user['photo_url']
        if photo and photo.filename:
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'photos')
            os.makedirs(upload_dir, exist_ok=True)
            ext = photo.filename.rsplit('.', 1)[-1].lower()
            filename = f"{uid}.{ext}"
            photo.save(os.path.join(upload_dir, filename))
            photo_url = f"uploads/photos/{filename}"
        db.execute("UPDATE users SET full_name=?,phone=?,email=?,address=?,photo_url=? WHERE id=?",
                   (full_name, phone, email, address, photo_url, uid))
        db.commit()
        session['name'] = full_name
        flash('Profile updated.', 'success')
        db.close()
        return redirect(url_for('warden.profile'))
    db.close()
    return render_template('shared/profile.html', user=user)
