from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
import sqlite3, os
from datetime import date, timedelta, datetime
from functools import wraps

def pivot_menu_rows(rows):
    """Convert a list of weekly_menus rows into a dict keyed by meal type.
    Returns a single dict: {breakfast_veg, breakfast_nonveg, lunch_veg, lunch_nonveg,
                            snacks_veg, snacks_nonveg, dinner_veg, dinner_nonveg}
    """
    d = {}
    for r in rows:
        mt = r['meal_type']
        d[f'{mt}_veg']    = r['veg_items']
        d[f'{mt}_nonveg'] = r['non_veg_items'] or r['veg_items']
    return d if d else None

def build_week_menu(rows, today):
    """Group raw weekly_menus rows into a list of per-day dicts for the food table."""
    from collections import defaultdict
    import calendar as cal_mod
    by_date = defaultdict(list)
    for r in rows:
        by_date[r['menu_date']].append(r)
    days = []
    for menu_date in sorted(by_date.keys()):
        pivoted = pivot_menu_rows(by_date[menu_date])
        dt = date.fromisoformat(menu_date)
        pivoted['date']     = menu_date
        pivoted['day_name'] = cal_mod.day_name[dt.weekday()]
        pivoted['is_today'] = (menu_date == today)
        days.append(pivoted)
    return days

student_bp = Blueprint('student', __name__)

def get_db():
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@student_bp.route('/dashboard')
@student_required
def dashboard():
    db  = get_db()
    sid = session.get('student_id')
    student = db.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    allot   = db.execute("""SELECT ra.*, r.room_number, r.floor_label, h.name as hostel_name
                             FROM room_allotments ra JOIN rooms r ON r.id=ra.room_id
                             JOIN hostels h ON h.id=r.hostel_id
                             WHERE ra.student_id=? AND ra.is_current=1""", (sid,)).fetchone()
    roommate = None
    if allot:
        roommate = db.execute("""SELECT s.name, s.usn, s.programme FROM students s
                                  JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
                                  WHERE ra.room_id=? AND s.id!=? AND ra.is_current=1 LIMIT 1""",
                               (allot['room_id'], sid)).fetchone()
    today   = date.today().isoformat()
    this_month_start = date.today().replace(day=1).isoformat()
    att_stats = db.execute("""
        SELECT SUM(CASE WHEN ar.status='present' THEN 1 ELSE 0 END) as present,
               SUM(CASE WHEN ar.status='absent'  THEN 1 ELSE 0 END) as absent,
               COUNT(*) as total
        FROM attendance_records ar
        JOIN attendance_sessions asn ON asn.id=ar.session_id
        WHERE ar.student_id=? AND asn.session_date BETWEEN ? AND ?
    """, (sid, this_month_start, today)).fetchone()
    active_perm = db.execute("""SELECT * FROM permission_requests WHERE student_id=?
                                 AND status IN ('pending','approved')
                                 ORDER BY submitted_at DESC LIMIT 1""", (sid,)).fetchone()
    raw_menu = db.execute("""SELECT * FROM weekly_menus WHERE hostel_id=? AND menu_date=?
                              ORDER BY meal_type""", (session.get('hostel_id'), today)).fetchall()
    today_menu = pivot_menu_rows(raw_menu)
    recent_complaints = db.execute("""SELECT * FROM food_complaints WHERE student_id=?
                                       ORDER BY submitted_at DESC LIMIT 3""", (sid,)).fetchall()
    db.close()

    # Build attendance dict with pct for template
    present = att_stats['present'] or 0 if att_stats else 0
    absent  = att_stats['absent']  or 0 if att_stats else 0
    total   = att_stats['total']   or 0 if att_stats else 0
    pct     = round(present / total * 100, 1) if total else 0
    attendance = {'present': present, 'absent': absent, 'total': total,
                  'on_leave': 0, 'pct': pct}

    food_pref = student['food_preference'] if student else 'veg'

    # Merge allot info into student-like dict for template
    student_ctx = dict(student) if student else {}
    if allot:
        student_ctx['room_number']  = allot['room_number']
        student_ctx['hostel_name']  = allot['hostel_name']
        student_ctx['floor_label']  = allot['floor_label']

    return render_template('student/dashboard.html',
        student=student_ctx, allot=allot, roommate=roommate,
        att_stats=att_stats, attendance=attendance,
        active_perm=active_perm, active_permission=active_perm,
        today_menu=today_menu, today=today,
        recent_complaints=recent_complaints,
        food_pref=food_pref)

@student_bp.route('/attendance')
@student_required
def attendance():
    db  = get_db()
    sid = session['student_id']
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    from_d = f"{month}-01"
    import calendar
    y,m = map(int, month.split('-'))
    last_day = calendar.monthrange(y,m)[1]
    to_d = f"{month}-{last_day:02d}"
    records = db.execute("""
        SELECT asn.session_date, ar.status
        FROM attendance_records ar
        JOIN attendance_sessions asn ON asn.id=ar.session_id
        WHERE ar.student_id=? AND asn.session_date BETWEEN ? AND ?
        ORDER BY asn.session_date
    """, (sid, from_d, to_d)).fetchall()
    att_map = {r['session_date']: r['status'] for r in records}
    total_p = sum(1 for v in att_map.values() if v=='present')
    total_a = sum(1 for v in att_map.values() if v=='absent')
    db.close()
    total_days = total_p + total_a
    pct = round(total_p / total_days * 100, 1) if total_days else 0
    summary = {'present': total_p, 'absent': total_a, 'on_leave': 0,
               'total': total_days, 'pct': pct}
    return render_template('student/attendance.html',
        att_map=att_map, month=month, from_d=from_d, to_d=to_d,
        total_p=total_p, total_a=total_a, summary=summary)

@student_bp.route('/permissions', methods=['GET','POST'])
@student_required
def permissions():
    db  = get_db()
    sid = session['student_id']
    if request.method == 'POST':
        ptype   = request.form.get('permission_type') or request.form.get('type')
        reason  = request.form.get('reason','').strip()
        from_d  = request.form.get('from_date')
        to_d    = request.form.get('to_date')
        parent_contact = request.form.get('parent_contact','').strip()
        if not all([ptype, reason, from_d, to_d]):
            flash('All fields are required', 'error')
        else:
            db.execute("""INSERT INTO permission_requests(student_id,permission_type,reason,from_date,to_date,parent_contact)
                          VALUES(?,?,?,?,?,?)""", (sid,ptype,reason,from_d,to_d,parent_contact or None))
            db.commit()
            flash('Permission request submitted. Warden will review it.', 'success')
            return redirect(url_for('student.permissions'))
    perms = db.execute("""SELECT * FROM permission_requests WHERE student_id=?
                           ORDER BY submitted_at DESC""", (sid,)).fetchall()
    db.close()
    return render_template('student/permissions.html', perms=perms)

@student_bp.route('/permissions/<int:pid>/cancel', methods=['POST'])
@student_required
def cancel_permission(pid):
    db  = get_db()
    sid = session['student_id']
    db.execute("UPDATE permission_requests SET status='cancelled' WHERE id=? AND student_id=? AND status='pending'",
               (pid, sid))
    db.commit()
    db.close()
    flash('Permission request cancelled', 'info')
    return redirect(url_for('student.permissions'))

@student_bp.route('/food', methods=['GET','POST'])
@student_required
def food():
    db  = get_db()
    sid = session['student_id']
    hid = session.get('hostel_id')
    student = db.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if request.method == 'POST':
        pref = request.form.get('food_pref') or request.form.get('preference','veg')
        db.execute("UPDATE students SET food_preference=? WHERE id=?", (pref, sid))
        db.commit()
        flash('Food preference updated', 'success')
        return redirect(url_for('student.food'))
    today = date.today().isoformat()
    week_end = (date.today() + timedelta(days=6)).isoformat()
    raw_rows = db.execute("""SELECT * FROM weekly_menus WHERE hostel_id=? AND menu_date BETWEEN ? AND ?
                              ORDER BY menu_date, meal_type""", (hid, today, week_end)).fetchall()
    week_menu = build_week_menu(raw_rows, today)
    current_pref = student['food_preference'] if student else 'veg'
    db.close()
    return render_template('student/food.html',
        student=student, week_menu=week_menu, current_pref=current_pref)

@student_bp.route('/complaints', methods=['GET','POST'])
@student_required
def complaints():
    db  = get_db()
    sid = session['student_id']
    hid = session.get('hostel_id')
    if request.method == 'POST':
        meal_date = request.form.get('date', date.today().isoformat())
        meal_type = request.form.get('meal_type','general')
        category  = request.form.get('category','other')
        desc      = request.form.get('description','').strip()
        if not desc:
            flash('Please describe the complaint', 'error')
        else:
            photo_url = None
            photo = request.files.get('photo')
            if photo and photo.filename:
                upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'complaints')
                os.makedirs(upload_dir, exist_ok=True)
                ext = photo.filename.rsplit('.', 1)[-1].lower()
                fname = f"c_{sid}_{int(datetime.now().timestamp())}.{ext}"
                photo.save(os.path.join(upload_dir, fname))
                photo_url = f"uploads/complaints/{fname}"
            db.execute("""INSERT INTO food_complaints(student_id,hostel_id,meal_date,meal_type,category,description,photo_url)
                          VALUES(?,?,?,?,?,?,?)""", (sid,hid,meal_date,meal_type,category,desc,photo_url))
            db.commit()
            flash('Complaint submitted', 'success')
            return redirect(url_for('student.complaints'))
    my_complaints = db.execute("""SELECT * FROM food_complaints WHERE student_id=?
                                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
    db.close()
    return render_template('student/complaints.html', complaints=my_complaints)

# ─────────────────────────────────────────────────────────────
# MOVEMENT LOG
# ─────────────────────────────────────────────────────────────
@student_bp.route('/movement', methods=['GET','POST'])
@student_required
def movement():
    db  = get_db()
    sid = session['student_id']
    hid = session.get('hostel_id')
    hostel = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    is_girls = hostel and hostel['code'] == 'G'
    curfew   = '7:30 PM' if is_girls else '9:30 PM'

    if request.method == 'POST':
        action = request.form.get('action','out')
        now    = datetime.now().isoformat(timespec='seconds')
        if action == 'out':
            reason   = request.form.get('reason','').strip()
            expected = request.form.get('expected_return','').strip() or None
            if not reason:
                flash('Please provide a reason.', 'error')
            else:
                db.execute("""INSERT INTO movement_logs(student_id,hostel_id,out_time,
                              expected_return,reason,status,recorded_by,created_at)
                              VALUES(?,?,?,?,?,'out',?,?)""",
                           (sid, hid, now, expected, reason, sid, now))
                db.commit()
                flash('You have been signed out. Stay safe!', 'success')
        elif action == 'in':
            db.execute("""UPDATE movement_logs SET in_time=?, status='returned'
                          WHERE student_id=? AND hostel_id=? AND status='out'""",
                       (now, sid, hid))
            db.commit()
            flash('Welcome back! You have been signed in.', 'success')
        db.close()
        return redirect(url_for('student.movement'))

    # current status
    current_out = db.execute("""SELECT * FROM movement_logs WHERE student_id=? AND status='out'
                                 ORDER BY out_time DESC LIMIT 1""", (sid,)).fetchone()
    today = date.today().isoformat()
    today_logs = db.execute("""SELECT * FROM movement_logs WHERE student_id=?
                                AND date(out_time)=?
                                ORDER BY out_time DESC""", (sid, today)).fetchall()
    db.close()
    return render_template('student/movement.html',
        hostel=hostel, curfew=curfew, is_girls=is_girls,
        current_out=current_out, today_logs=today_logs)

# ─────────────────────────────────────────────────────────────
# CIRCULARS
# ─────────────────────────────────────────────────────────────
@student_bp.route('/circulars')
@student_required
def circulars():
    db  = get_db()
    hid = session.get('hostel_id')
    hostel = db.execute("SELECT code FROM hostels WHERE id=?", (hid,)).fetchone()
    hostel_code = hostel['code'].lower() if hostel else 'b'
    target_label = 'girls' if hostel_code == 'g' else 'boys'
    circulars = db.execute("""
        SELECT c.*, u.full_name as author
        FROM circulars c JOIN users u ON u.id=c.published_by
        WHERE c.is_active=1
          AND (c.target='all' OR c.target='students'
               OR c.target=?)
        ORDER BY c.is_pinned DESC, c.published_at DESC
    """, (target_label,)).fetchall()
    db.close()
    return render_template('student/circulars.html', circulars=circulars)

# ─────────────────────────────────────────────────────────────
# PROTOCOLS
# ─────────────────────────────────────────────────────────────
@student_bp.route('/protocols')
@student_required
def protocols():
    db = get_db()
    hid = session.get('hostel_id')
    hostel   = db.execute("SELECT * FROM hostels WHERE id=?", (hid,)).fetchone()
    wardens  = db.execute("SELECT full_name, phone, role FROM users WHERE role IN ('warden_boys','warden_girls') AND is_active=1").fetchall()
    chairman = db.execute("SELECT full_name, phone FROM users WHERE role='chairman' AND is_active=1 LIMIT 1").fetchone()
    db.close()
    return render_template('shared/protocols.html',
        hostel=hostel, wardens=wardens, chairman=chairman,
        is_girls=(hostel and hostel['code']=='G'))

# ─────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────
@student_bp.route('/profile', methods=['GET','POST'])
@student_required
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
        return redirect(url_for('student.profile'))
    db.close()
    return render_template('shared/profile.html', user=user)
