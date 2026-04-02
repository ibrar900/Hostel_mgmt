from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, Response
import sqlite3, csv, os
from datetime import date, datetime
from functools import wraps
from io import StringIO

office_bp = Blueprint('office', __name__)

def get_db():
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def office_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'office':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────
@office_bp.route('/dashboard')
@office_required
def dashboard():
    db = get_db()
    total_students   = db.execute("SELECT COUNT(*) FROM students WHERE is_active=1").fetchone()[0]
    total_collected  = db.execute("SELECT COALESCE(SUM(paid_amount),0) FROM fees").fetchone()[0]
    total_billed     = db.execute("SELECT COALESCE(SUM(total_amount),0) FROM fees").fetchone()[0]
    total_dues       = max(total_billed - total_collected, 0)
    due_count        = db.execute("""
        SELECT COUNT(DISTINCT student_id) FROM fees
        WHERE total_amount > paid_amount""").fetchone()[0]
    paid_count       = db.execute("""
        SELECT COUNT(DISTINCT student_id) FROM fees
        WHERE total_amount > 0 AND paid_amount >= total_amount""").fetchone()[0]
    open_complaints  = db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='open'").fetchone()[0]
    recent_circulars = db.execute("""SELECT c.*, u.full_name as author FROM circulars c
                                     JOIN users u ON u.id=c.published_by
                                     WHERE c.is_active=1
                                     ORDER BY c.published_at DESC LIMIT 5""").fetchall()
    db.close()
    return render_template('office/dashboard.html',
        total_students=total_students,
        total_collected=total_collected,
        total_dues=total_dues,
        due_count=due_count,
        paid_count=paid_count,
        open_complaints=open_complaints,
        recent_circulars=recent_circulars)

# ─────────────────────────────────────────────────────────────
# STUDENTS
# ─────────────────────────────────────────────────────────────
@office_bp.route('/students')
@office_required
def students():
    db      = get_db()
    q       = request.args.get('q','').strip()
    hfilter = request.args.get('hostel','all')
    prog    = request.args.get('programme','').strip()
    sem     = request.args.get('semester','').strip()
    page    = int(request.args.get('page', 1)); per_page = 25
    qry = """SELECT s.*, r.room_number, h.name as hostel_name, h.code as hostel_code,
                    COALESCE(SUM(f.total_amount),0) as total_fees,
                    COALESCE(SUM(f.paid_amount),0)  as paid_fees
             FROM students s
             LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
             LEFT JOIN rooms r ON r.id=ra.room_id
             LEFT JOIN hostels h ON h.id=r.hostel_id
             LEFT JOIN fees f ON f.student_id=s.id
             WHERE s.is_active=1 """
    params = []
    if q:    qry += " AND (s.name LIKE ? OR s.usn LIKE ?)"; params += [f'%{q}%', f'%{q}%']
    if hfilter == 'B': qry += " AND h.code='B'"
    if hfilter == 'G': qry += " AND h.code='G'"
    if prog: qry += " AND s.programme LIKE ?"; params.append(f'%{prog}%')
    if sem:  qry += " AND s.semester=?";       params.append(sem)
    qry += " GROUP BY s.id ORDER BY h.code, r.room_number, s.name"
    all_s = db.execute(qry, params).fetchall()
    total = len(all_s)
    stu   = all_s[(page-1)*per_page : page*per_page]
    db.close()
    return render_template('office/students.html',
        students=stu, total=total, page=page, per_page=per_page,
        q=q, hfilter=hfilter, prog=prog, sem=sem)

# ─────────────────────────────────────────────────────────────
# FEES
# ─────────────────────────────────────────────────────────────
@office_bp.route('/fees')
@office_required
def fees():
    db      = get_db()
    q       = request.args.get('q','').strip()
    hfilter = request.args.get('hostel','all')
    status_f= request.args.get('status','all')
    qry = """SELECT s.id, s.name, s.usn, r.room_number, h.name as hostel_name, h.code as hostel_code,
                    COALESCE(SUM(f.total_amount),0) as total_amount,
                    COALESCE(SUM(f.paid_amount),0)  as paid_amount,
                    f.due_date, f.academic_year, f.fee_type, f.notes
             FROM students s
             LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
             LEFT JOIN rooms r ON r.id=ra.room_id
             LEFT JOIN hostels h ON h.id=r.hostel_id
             LEFT JOIN fees f ON f.student_id=s.id
             WHERE s.is_active=1 """
    params = []
    if q:    qry += " AND (s.name LIKE ? OR s.usn LIKE ?)"; params += [f'%{q}%', f'%{q}%']
    if hfilter == 'B': qry += " AND h.code='B'"
    if hfilter == 'G': qry += " AND h.code='G'"
    qry += " GROUP BY s.id ORDER BY h.code, r.room_number, s.name"
    all_s   = db.execute(qry, params).fetchall()
    students = []
    for s in all_s:
        due = max((s['total_amount'] or 0) - (s['paid_amount'] or 0), 0)
        if status_f == 'due'     and due <= 0:             continue
        if status_f == 'paid'    and (s['total_amount'] == 0 or due > 0): continue
        if status_f == 'partial' and not (s['paid_amount'] > 0 and due > 0): continue
        if status_f == 'no_record' and s['total_amount'] > 0: continue
        students.append(s)
    total_collected = sum((s['paid_amount'] or 0) for s in students)
    total_dues      = sum(max((s['total_amount'] or 0) - (s['paid_amount'] or 0), 0) for s in students)
    db.close()
    return render_template('office/fees.html',
        students=students, total_collected=total_collected, total_dues=total_dues,
        q=q, hfilter=hfilter, status_f=status_f)

# ─────────────────────────────────────────────────────────────
# NOTIFICATIONS
# ─────────────────────────────────────────────────────────────
@office_bp.route('/notifications', methods=['GET','POST'])
@office_required
def notifications():
    db = get_db()
    if request.method == 'POST':
        title   = request.form.get('title','').strip()
        body    = request.form.get('body','').strip()
        target  = request.form.get('target','all')  # all / student_id
        now     = datetime.now().isoformat(timespec='seconds')
        if not title or not body:
            flash('Title and message are required.', 'error')
        else:
            if target == 'all':
                users = db.execute("SELECT id FROM users WHERE is_active=1").fetchall()
                for u in users:
                    db.execute("INSERT INTO notifications(user_id,title,body,is_read,created_at) VALUES(?,?,?,0,?)",
                               (u['id'], title, body, now))
            else:
                uid = int(target)
                db.execute("INSERT INTO notifications(user_id,title,body,is_read,created_at) VALUES(?,?,?,0,?)",
                           (uid, title, body, now))
            db.commit()
            flash('Notification sent.', 'success')
        db.close()
        return redirect(url_for('office.notifications'))
    students = db.execute("""SELECT s.id, s.name, s.usn, u.id as user_id
                              FROM students s JOIN users u ON u.id=s.user_id
                              WHERE s.is_active=1 ORDER BY s.name""").fetchall()
    recent = db.execute("""SELECT n.*, u.full_name, u.username
                            FROM notifications n JOIN users u ON u.id=n.user_id
                            ORDER BY n.created_at DESC LIMIT 50""").fetchall()
    db.close()
    return render_template('office/notifications.html', students=students, recent=recent)

# ─────────────────────────────────────────────────────────────
# CIRCULARS
# ─────────────────────────────────────────────────────────────
@office_bp.route('/circulars', methods=['GET','POST'])
@office_required
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
        return redirect(url_for('office.circulars'))
    all_circulars = db.execute("""SELECT c.*, u.full_name as author
                                   FROM circulars c JOIN users u ON u.id=c.published_by
                                   ORDER BY c.is_pinned DESC, c.published_at DESC""").fetchall()
    db.close()
    return render_template('office/circulars.html', circulars=all_circulars)

@office_bp.route('/circulars/<int:cid>/delete', methods=['POST'])
@office_required
def delete_circular(cid):
    db = get_db()
    db.execute("UPDATE circulars SET is_active=0 WHERE id=?", (cid,))
    db.commit()
    db.close()
    flash('Circular deactivated.', 'info')
    return redirect(url_for('office.circulars'))

# ─────────────────────────────────────────────────────────────
# COMPLAINTS (view only)
# ─────────────────────────────────────────────────────────────
@office_bp.route('/complaints')
@office_required
def complaints():
    db       = get_db()
    status_f = request.args.get('status','all')
    cat_f    = request.args.get('category','all')
    hfilter  = request.args.get('hostel','all')
    qry = """SELECT fc.*, s.name as student_name, s.usn, r.room_number,
                    h.name as hostel_name, h.code as hostel_code
             FROM food_complaints fc
             JOIN students s ON s.id=fc.student_id
             LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
             LEFT JOIN rooms r ON r.id=ra.room_id
             LEFT JOIN hostels h ON h.id=r.hostel_id
             WHERE 1=1 """
    params = []
    if status_f != 'all': qry += " AND fc.status=?";   params.append(status_f)
    if cat_f    != 'all': qry += " AND fc.category=?"; params.append(cat_f)
    if hfilter  == 'B':   qry += " AND h.code='B'"
    if hfilter  == 'G':   qry += " AND h.code='G'"
    qry += " ORDER BY fc.submitted_at DESC"
    comps = db.execute(qry, params).fetchall()
    stats = {
        'open':         db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='open'").fetchone()[0],
        'acknowledged': db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='acknowledged'").fetchone()[0],
        'resolved':     db.execute("SELECT COUNT(*) FROM food_complaints WHERE status='resolved'").fetchone()[0],
    }
    db.close()
    return render_template('office/complaints.html',
        complaints=comps, stats=stats,
        status_filter=status_f, cat_filter=cat_f, hfilter=hfilter)

# ─────────────────────────────────────────────────────────────
# REPORTS
# ─────────────────────────────────────────────────────────────
@office_bp.route('/reports')
@office_required
def reports():
    db      = get_db()
    rtype   = request.args.get('type','fees')
    from_d  = request.args.get('from', date.today().replace(day=1).isoformat())
    to_d    = request.args.get('to',   date.today().isoformat())
    hfilter = request.args.get('hostel','all')
    status_f= request.args.get('status','all')
    fmt     = request.args.get('fmt','html')
    data    = []
    hostel_clause = ""
    if hfilter == 'B': hostel_clause = " AND h.code='B'"
    if hfilter == 'G': hostel_clause = " AND h.code='G'"

    if rtype == 'fees':
        status_clause = ""
        if status_f == 'due':     status_clause = " HAVING (COALESCE(SUM(f.total_amount),0) - COALESCE(SUM(f.paid_amount),0)) > 0"
        elif status_f == 'paid':  status_clause = " HAVING COALESCE(SUM(f.total_amount),0) > 0 AND COALESCE(SUM(f.paid_amount),0) >= COALESCE(SUM(f.total_amount),0)"
        elif status_f == 'partial': status_clause = " HAVING COALESCE(SUM(f.paid_amount),0) > 0 AND (COALESCE(SUM(f.total_amount),0) - COALESCE(SUM(f.paid_amount),0)) > 0"
        data = db.execute(f"""
            SELECT h.name as hostel, s.name, s.usn, r.room_number,
                   COALESCE(SUM(f.total_amount),0) as total_amount,
                   COALESCE(SUM(f.paid_amount),0)  as paid_amount,
                   COALESCE(SUM(f.total_amount),0) - COALESCE(SUM(f.paid_amount),0) as due_amount,
                   MAX(f.due_date) as due_date, MAX(f.fee_type) as fee_type
            FROM students s
            LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            LEFT JOIN rooms r ON r.id=ra.room_id
            LEFT JOIN hostels h ON h.id=r.hostel_id
            LEFT JOIN fees f ON f.student_id=s.id
            WHERE s.is_active=1 {hostel_clause}
            GROUP BY s.id {status_clause}
            ORDER BY h.code, r.room_number, s.name
        """).fetchall()

    elif rtype == 'students':
        data = db.execute(f"""
            SELECT h.name as hostel, s.name, s.usn, r.room_number,
                   s.programme, s.semester, s.phone, s.email,
                   s.admission_date, s.food_preference
            FROM students s
            LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            LEFT JOIN rooms r ON r.id=ra.room_id
            LEFT JOIN hostels h ON h.id=r.hostel_id
            WHERE s.is_active=1 {hostel_clause}
            ORDER BY h.code, r.room_number, s.name
        """).fetchall()

    elif rtype == 'complaints':
        cat_f = request.args.get('category','all')
        cat_clause = "" if cat_f == 'all' else f" AND fc.category='{cat_f}'"
        s_clause = "" if status_f == 'all' else f" AND fc.status='{status_f}'"
        data = db.execute(f"""
            SELECT h.name as hostel, s.name, s.usn, fc.meal_date, fc.category,
                   fc.description, fc.status, fc.submitted_at
            FROM food_complaints fc
            JOIN students s ON s.id=fc.student_id
            LEFT JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            LEFT JOIN rooms r ON r.id=ra.room_id
            LEFT JOIN hostels h ON h.id=r.hostel_id
            WHERE fc.submitted_at BETWEEN ? AND ? {hostel_clause}{cat_clause}{s_clause}
            ORDER BY fc.submitted_at DESC
        """, (from_d, to_d)).fetchall()

    if fmt == 'csv':
        si = StringIO()
        cw = csv.writer(si)
        if data:
            cw.writerow(data[0].keys())
            for row in data: cw.writerow(list(row))
        si.seek(0)
        db.close()
        return Response(si, mimetype='text/csv',
            headers={'Content-Disposition': f'attachment;filename=office_{rtype}_{from_d}_{to_d}.csv'})

    db.close()
    return render_template('office/reports.html',
        rtype=rtype, from_d=from_d, to_d=to_d, data=data, fmt=fmt,
        hfilter=hfilter, status_f=status_f,
        cat_filter=request.args.get('category','all'))

# ─────────────────────────────────────────────────────────────
# PROFILE
# ─────────────────────────────────────────────────────────────
@office_bp.route('/profile', methods=['GET','POST'])
@office_required
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
        return redirect(url_for('office.profile'))
    db.close()
    return render_template('shared/profile.html', user=user)
