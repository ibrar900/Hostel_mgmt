from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, Response
import sqlite3, csv, os
from datetime import date, datetime
from functools import wraps
from io import StringIO

chairman_bp = Blueprint('chairman', __name__)

def get_db():
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def chairman_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'chairman':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@chairman_bp.route('/dashboard')
@chairman_required
def dashboard():
    db    = get_db()
    today = date.today().isoformat()
    hostels = db.execute("SELECT * FROM hostels ORDER BY code").fetchall()
    host_data = []
    for h in hostels:
        total = db.execute("""SELECT COUNT(*) FROM students s
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id WHERE r.hostel_id=? AND s.is_active=1""",(h['id'],)).fetchone()[0]
        sess  = db.execute("SELECT id FROM attendance_sessions WHERE hostel_id=? AND session_date=?",(h['id'],today)).fetchone()
        present = absent = 0
        if sess:
            present = db.execute("SELECT COUNT(*) FROM attendance_records WHERE session_id=? AND status='present'",(sess['id'],)).fetchone()[0]
            absent  = db.execute("SELECT COUNT(*) FROM attendance_records WHERE session_id=? AND status='absent'",(sess['id'],)).fetchone()[0]
        pending_p = db.execute("""SELECT COUNT(*) FROM permission_requests pr
            JOIN students s ON s.id=pr.student_id
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id WHERE r.hostel_id=? AND pr.status='pending'""",(h['id'],)).fetchone()[0]
        open_c = db.execute("SELECT COUNT(*) FROM food_complaints WHERE hostel_id=? AND status='open'",(h['id'],)).fetchone()[0]
        veg_c  = db.execute("""SELECT COUNT(*) FROM students s
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id WHERE r.hostel_id=? AND s.food_preference='veg' AND s.is_active=1""",(h['id'],)).fetchone()[0]
        host_data.append({'hostel':h,'total':total,'present':present,'absent':absent,
                          'pending_perms':pending_p,'open_complaints':open_c,'veg':veg_c,'nv':total-veg_c})

    # 30-day attendance trend
    from datetime import timedelta
    trend_dates = [(date.today()-timedelta(days=i)).isoformat() for i in range(29,-1,-1)]
    boys_id  = db.execute("SELECT id FROM hostels WHERE code='B'").fetchone()['id']
    girls_id = db.execute("SELECT id FROM hostels WHERE code='G'").fetchone()['id']
    boys_trend  = []
    girls_trend = []
    for d in trend_dates:
        bs = db.execute("""SELECT COUNT(*) FROM attendance_records ar JOIN attendance_sessions asn ON asn.id=ar.session_id
            WHERE asn.hostel_id=? AND asn.session_date=? AND ar.status='present'""",(boys_id,d)).fetchone()[0]
        gs = db.execute("""SELECT COUNT(*) FROM attendance_records ar JOIN attendance_sessions asn ON asn.id=ar.session_id
            WHERE asn.hostel_id=? AND asn.session_date=? AND ar.status='present'""",(girls_id,d)).fetchone()[0]
        boys_trend.append(bs); girls_trend.append(gs)

    total_students   = db.execute("SELECT COUNT(*) FROM students WHERE is_active=1").fetchone()[0]
    total_perms      = db.execute("SELECT COUNT(*) FROM permission_requests WHERE status='approved'").fetchone()[0]
    pending_perms    = db.execute("SELECT COUNT(*) FROM permission_requests WHERE status='pending'").fetchone()[0]
    total_complaints = db.execute("SELECT COUNT(*) FROM food_complaints").fetchone()[0]
    open_complaints  = db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='open'").fetchone()[0]
    present_today    = sum(h['present'] for h in host_data)
    present_pct      = round(present_today / total_students * 100, 1) if total_students else 0

    overall = {
        'total_students':    total_students,
        'present_today':     present_today,
        'present_pct':       present_pct,
        'total_permissions': total_perms,
        'pending_permissions': pending_perms,
        'total_complaints':  total_complaints,
        'open_complaints':   open_complaints,
    }

    # split host_data into boys and girls for template
    boys  = next((d for d in host_data if d['hostel']['code']=='B'), {})
    girls = next((d for d in host_data if d['hostel']['code']=='G'), {})
    # template uses boys.veg / boys.nonveg — map 'nv' -> 'nonveg'
    boys  = dict(boys,  nonveg=boys.get('nv',0),  hostel_name='Boys Hostel',
                 pending_permissions=boys.get('pending_perms',0),
                 open_complaints=boys.get('open_complaints',0))
    girls = dict(girls, nonveg=girls.get('nv',0), hostel_name='Girls Hostel',
                 pending_permissions=girls.get('pending_perms',0),
                 open_complaints=girls.get('open_complaints',0))

    db.close()
    return render_template('chairman/dashboard.html',
        host_data=host_data, today=today, overall=overall,
        boys=boys, girls=girls,
        trend_labels=trend_dates, boys_trend=boys_trend, girls_trend=girls_trend)

@chairman_bp.route('/students')
@chairman_required
def students():
    db   = get_db()
    q    = request.args.get('q','').strip()
    hfilter = request.args.get('hostel','all')
    page = int(request.args.get('page',1)); per_page = 25
    qry  = """SELECT s.*, r.room_number, h.name as hostel_name, h.code as hostel_code
              FROM students s
              LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
              LEFT JOIN rooms r ON r.id=ra.room_id
              LEFT JOIN hostels h ON h.id=r.hostel_id
              WHERE s.is_active=1 """
    params = []
    if q:     qry += " AND (s.name LIKE ? OR s.usn LIKE ?)"; params += [f'%{q}%',f'%{q}%']
    if hfilter == 'B': qry += " AND h.code='B'"
    if hfilter == 'G': qry += " AND h.code='G'"
    qry += " ORDER BY h.code, r.room_number, s.name"
    all_s = db.execute(qry, params).fetchall()
    total = len(all_s)
    stu   = all_s[(page-1)*per_page:page*per_page]
    db.close()
    return render_template('chairman/students.html', students=stu, total=total, page=page,
                           per_page=per_page, q=q, hfilter=hfilter)

@chairman_bp.route('/permissions')
@chairman_required
def permissions():
    db = get_db()
    status_f = request.args.get('status','pending')
    hfilter  = request.args.get('hostel','all')
    qry = """SELECT pr.*, s.name, s.usn, r.room_number, h.name as hostel_name
             FROM permission_requests pr
             JOIN students s ON s.id=pr.student_id
             LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
             LEFT JOIN rooms r ON r.id=ra.room_id
             LEFT JOIN hostels h ON h.id=r.hostel_id
             WHERE pr.status=? """
    params = [status_f]
    if hfilter == 'B': qry += " AND h.code='B'"
    if hfilter == 'G': qry += " AND h.code='G'"
    qry += " ORDER BY pr.submitted_at DESC"
    perms = db.execute(qry, params).fetchall()
    db.close()
    return render_template('chairman/permissions.html', perms=perms,
                           status_filter=status_f, hfilter=hfilter)

@chairman_bp.route('/complaints')
@chairman_required
def complaints():
    db = get_db()
    status_f = request.args.get('status','open')
    comps = db.execute("""
        SELECT fc.*, s.name, s.usn, r.room_number, h.name as hostel_name
        FROM food_complaints fc
        JOIN students s ON s.id=fc.student_id
        LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
        LEFT JOIN rooms r ON r.id=ra.room_id
        LEFT JOIN hostels h ON h.id=r.hostel_id
        WHERE fc.status=? ORDER BY fc.submitted_at DESC
    """, (status_f,)).fetchall()
    stats = {
        'open':         db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='open'").fetchone()[0],
        'acknowledged': db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='acknowledged'").fetchone()[0],
        'resolved':     db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='resolved'").fetchone()[0],
    }
    db.close()
    return render_template('chairman/complaints.html', complaints=comps, status_filter=status_f, stats=stats)

@chairman_bp.route('/reports')
@chairman_required
def reports():
    db       = get_db()
    rtype    = request.args.get('type', 'attendance')
    from_d   = request.args.get('from', date.today().replace(day=1).isoformat())
    to_d     = request.args.get('to',   date.today().isoformat())
    hfilter  = request.args.get('hostel', 'all')
    status_f = request.args.get('status', 'all')
    cat_filter = request.args.get('category', 'all')
    fmt      = request.args.get('fmt', 'html')
    data     = []
    hostel_clause = ""
    if hfilter == 'B': hostel_clause = " AND h.code='B'"
    if hfilter == 'G': hostel_clause = " AND h.code='G'"

    if rtype == 'attendance':
        data = db.execute(f"""
            SELECT h.name as hostel, s.name, s.usn, r.room_number,
              SUM(CASE WHEN ar.status='present' THEN 1 ELSE 0 END) as present_days,
              SUM(CASE WHEN ar.status='absent'  THEN 1 ELSE 0 END) as absent_days,
              SUM(CASE WHEN ar.status='on_leave' THEN 1 ELSE 0 END) as leave_days,
              COUNT(ar.id) as total_days,
              ROUND(100.0*SUM(CASE WHEN ar.status='present' THEN 1 ELSE 0 END)/MAX(COUNT(ar.id),1),1) as pct
            FROM students s
            JOIN room_allotments ra2 ON ra2.student_id=s.id AND ra2.is_current=1
            JOIN rooms r ON r.id=ra2.room_id JOIN hostels h ON h.id=r.hostel_id
            LEFT JOIN attendance_records ar ON ar.student_id=s.id
            LEFT JOIN attendance_sessions asn ON asn.id=ar.session_id AND asn.session_date BETWEEN ? AND ?
            WHERE s.is_active=1 {hostel_clause}
            GROUP BY s.id ORDER BY h.code, r.room_number, s.name
        """, (from_d, to_d)).fetchall()

    elif rtype == 'permissions':
        qry = f"""SELECT h.name as hostel, s.name, s.usn, r.room_number,
                         pr.permission_type, pr.from_date, pr.to_date, pr.reason, pr.status
                  FROM permission_requests pr
                  JOIN students s ON s.id=pr.student_id
                  JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
                  JOIN rooms r ON r.id=ra.room_id JOIN hostels h ON h.id=r.hostel_id
                  WHERE pr.submitted_at BETWEEN ? AND ? {hostel_clause}"""
        params = [from_d, to_d]
        if status_f != 'all': qry += " AND pr.status=?"; params.append(status_f)
        qry += " ORDER BY pr.submitted_at DESC"
        data = db.execute(qry, params).fetchall()

    elif rtype == 'fees':
        status_clause = ""
        if status_f == 'due':     status_clause = " HAVING (COALESCE(SUM(f.total_amount),0)-COALESCE(SUM(f.paid_amount),0))>0"
        elif status_f == 'paid':  status_clause = " HAVING COALESCE(SUM(f.total_amount),0)>0 AND COALESCE(SUM(f.paid_amount),0)>=COALESCE(SUM(f.total_amount),0)"
        elif status_f == 'partial': status_clause = " HAVING COALESCE(SUM(f.paid_amount),0)>0 AND (COALESCE(SUM(f.total_amount),0)-COALESCE(SUM(f.paid_amount),0))>0"
        data = db.execute(f"""
            SELECT h.name as hostel, s.name, s.usn, r.room_number,
                   COALESCE(SUM(f.total_amount),0) as total_amount,
                   COALESCE(SUM(f.paid_amount),0)  as paid_amount,
                   COALESCE(SUM(f.total_amount),0)-COALESCE(SUM(f.paid_amount),0) as due_amount
            FROM students s
            JOIN room_allotments ra2 ON ra2.student_id=s.id AND ra2.is_current=1
            JOIN rooms r ON r.id=ra2.room_id JOIN hostels h ON h.id=r.hostel_id
            LEFT JOIN fees f ON f.student_id=s.id
            WHERE s.is_active=1 {hostel_clause}
            GROUP BY s.id {status_clause}
            ORDER BY h.code, r.room_number, s.name
        """).fetchall()

    elif rtype == 'food_complaints':
        qry = f"""SELECT h.name as hostel, s.name, s.usn, fc.meal_date,
                         fc.category, fc.description, fc.status, fc.submitted_at
                  FROM food_complaints fc
                  JOIN students s ON s.id=fc.student_id
                  JOIN hostels h ON h.id=fc.hostel_id
                  WHERE fc.submitted_at BETWEEN ? AND ? {hostel_clause}"""
        params = [from_d, to_d]
        if cat_filter != 'all': qry += " AND fc.category=?"; params.append(cat_filter)
        if status_f   != 'all': qry += " AND fc.status=?";   params.append(status_f)
        qry += " ORDER BY fc.submitted_at DESC"
        data = db.execute(qry, params).fetchall()

    if fmt == 'csv':
        si = StringIO()
        cw = csv.writer(si)
        if data:
            cw.writerow(data[0].keys())
            for row in data: cw.writerow(list(row))
        si.seek(0)
        db.close()
        return Response(si, mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename={rtype}_{from_d}_{to_d}.csv'})

    db.close()
    return render_template('chairman/reports.html',
        rtype=rtype, from_d=from_d, to_d=to_d, data=data, fmt=fmt,
        hfilter=hfilter, status_f=status_f, cat_filter=cat_filter)

@chairman_bp.route('/users', methods=['GET','POST'])
@chairman_required
def users():
    db = get_db()
    if request.method == 'POST':
        from werkzeug.security import generate_password_hash
        uname = request.form.get('username','').strip()
        pwd   = request.form.get('password','')
        role  = request.form.get('role','')
        name  = request.form.get('full_name','').strip()
        phone = request.form.get('phone','').strip()
        try:
            db.execute("INSERT INTO users(username,password_hash,role,full_name,phone) VALUES(?,?,?,?,?)",
                       (uname, generate_password_hash(pwd), role, name, phone))
            db.commit()
            flash(f'User {uname} created', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
    all_users = db.execute("SELECT * FROM users WHERE role != 'student' ORDER BY role, full_name").fetchall()
    db.close()
    return render_template('chairman/users.html', users=all_users)

@chairman_bp.route('/users/add', methods=['POST'])
@chairman_required
def add_user():
    from werkzeug.security import generate_password_hash
    db    = get_db()
    uname = request.form.get('username','').strip()
    pwd   = request.form.get('password','')
    role  = request.form.get('role','')
    name  = request.form.get('name','').strip()
    phone = request.form.get('phone','').strip()
    try:
        db.execute("INSERT INTO users(username,password_hash,role,full_name,phone) VALUES(?,?,?,?,?)",
                   (uname, generate_password_hash(pwd), role, name, phone))
        db.commit()
        flash(f'User {uname} created successfully', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'error')
    db.close()
    return redirect(url_for('chairman.users'))

@chairman_bp.route('/users/reset-password', methods=['POST'])
@chairman_required
def reset_password():
    from werkzeug.security import generate_password_hash
    db      = get_db()
    uid     = request.form.get('user_id', type=int)
    new_pwd = request.form.get('new_password','')
    if uid and new_pwd:
        db.execute("UPDATE users SET password_hash=? WHERE id=?",
                   (generate_password_hash(new_pwd), uid))
        db.commit()
        flash('Password reset successfully', 'success')
    else:
        flash('User and new password are required', 'error')
    db.close()
    return redirect(url_for('chairman.users'))

@chairman_bp.route('/users/<int:uid>/toggle', methods=['POST'])
@chairman_required
def toggle_user(uid):
    db = get_db()
    db.execute("UPDATE users SET is_active = 1 - is_active WHERE id=?", (uid,))
    db.commit()
    db.close()
    flash('User status updated', 'info')
    return redirect(url_for('chairman.users'))

# ─────────────────────────────────────────────────────────────
# CIRCULARS
# ─────────────────────────────────────────────────────────────
@chairman_bp.route('/circulars', methods=['GET','POST'])
@chairman_required
def circulars():
    db = get_db()
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
        return redirect(url_for('chairman.circulars'))

    all_circulars = db.execute("""SELECT c.*, u.full_name as author
                                   FROM circulars c JOIN users u ON u.id=c.published_by
                                   ORDER BY c.is_pinned DESC, c.published_at DESC""").fetchall()
    db.close()
    return render_template('chairman/circulars.html', circulars=all_circulars)

@chairman_bp.route('/circulars/<int:cid>/delete', methods=['POST'])
@chairman_required
def delete_circular(cid):
    db = get_db()
    db.execute("UPDATE circulars SET is_active=0 WHERE id=?", (cid,))
    db.commit()
    db.close()
    flash('Circular deactivated.', 'info')
    return redirect(url_for('chairman.circulars'))

# ─────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────
@chairman_bp.route('/profile', methods=['GET','POST'])
@chairman_required
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
        return redirect(url_for('chairman.profile'))
    db.close()
    return render_template('shared/profile.html', user=user)
