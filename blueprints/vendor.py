from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
import sqlite3
from datetime import date, timedelta
from functools import wraps

vendor_bp = Blueprint('vendor', __name__)

def get_db():
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def vendor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'vendor':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

@vendor_bp.route('/dashboard')
@vendor_required
def dashboard():
    db    = get_db()
    today = date.today().isoformat()
    hostels = db.execute("SELECT * FROM hostels ORDER BY code").fetchall()
    host_data = []
    for h in hostels:
        veg_count = db.execute("""
            SELECT COUNT(*) FROM students s
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id
            WHERE r.hostel_id=? AND s.is_active=1 AND s.food_preference='veg'
              AND s.id NOT IN (
                SELECT pr.student_id FROM permission_requests pr
                JOIN students st ON st.id=pr.student_id
                WHERE pr.status='approved' AND pr.from_date<=? AND pr.to_date>=?)
        """, (h['id'], today, today)).fetchone()[0]
        nv_count = db.execute("""
            SELECT COUNT(*) FROM students s
            JOIN room_allotments ra ON ra.student_id=s.id AND ra.is_current=1
            JOIN rooms r ON r.id=ra.room_id
            WHERE r.hostel_id=? AND s.is_active=1 AND s.food_preference='non-veg'
              AND s.id NOT IN (
                SELECT pr.student_id FROM permission_requests pr
                WHERE pr.status='approved' AND pr.from_date<=? AND pr.to_date>=?)
        """, (h['id'], today, today)).fetchone()[0]
        menu_rows = db.execute("SELECT * FROM weekly_menus WHERE hostel_id=? AND menu_date=? ORDER BY meal_type",
                               (h['id'], today)).fetchall()
        # Pivot into a single dict: breakfast_veg, lunch_veg, dinner_veg, etc.
        menu_pivot = {}
        for r in menu_rows:
            mt = r['meal_type']
            menu_pivot[f'{mt}_veg']    = r['veg_items']
            menu_pivot[f'{mt}_nonveg'] = r['non_veg_items'] or ''
        open_complaints = db.execute("SELECT COUNT(*) FROM food_complaints WHERE hostel_id=? AND status='open'",(h['id'],)).fetchone()[0]
        host_data.append({'hostel':h, 'veg':veg_count, 'nv':nv_count,
                          'nonveg': nv_count,
                          'menu': menu_pivot if menu_pivot else None,
                          'today_menu': menu_pivot if menu_pivot else None,
                          'open_complaints':open_complaints})
    # Split into boys/girls and compute totals
    boys  = next((d for d in host_data if d['hostel']['code']=='B'), {})
    girls = next((d for d in host_data if d['hostel']['code']=='G'), {})
    total_veg    = boys.get('veg',0)  + girls.get('veg',0)
    total_nonveg = boys.get('nv',0)   + girls.get('nv',0)
    db.close()
    return render_template('vendor/dashboard.html',
        host_data=host_data, today=today,
        boys=boys, girls=girls,
        total_veg=total_veg, total_nonveg=total_nonveg)

@vendor_bp.route('/menu', methods=['GET','POST'])
@vendor_required
def menu():
    db    = get_db()
    today = date.today().isoformat()
    if request.method == 'POST':
        hostel_id  = request.form.get('hostel_id')
        menu_date  = request.form.get('menu_date')
        meal_type  = request.form.get('meal_type')
        veg_items  = request.form.get('veg_items','').strip()
        nv_items   = request.form.get('non_veg_items','').strip()
        if not veg_items:
            flash('Veg items are required', 'error')
        else:
            db.execute("""INSERT INTO weekly_menus(hostel_id,menu_date,meal_type,veg_items,non_veg_items,uploaded_by)
                          VALUES(?,?,?,?,?,?)
                          ON CONFLICT(hostel_id,menu_date,meal_type) DO UPDATE SET
                          veg_items=excluded.veg_items, non_veg_items=excluded.non_veg_items""",
                       (hostel_id, menu_date, meal_type, veg_items, nv_items, session['user_id']))
            db.commit()
            flash('Menu saved', 'success')
            return redirect(url_for('vendor.menu'))
    hostels   = db.execute("SELECT * FROM hostels ORDER BY code").fetchall()
    week_start= date.today()
    week_dates= [(week_start + timedelta(days=i)).isoformat() for i in range(7)]
    menus = db.execute("""SELECT * FROM weekly_menus WHERE menu_date BETWEEN ? AND ?
                           ORDER BY hostel_id, menu_date, meal_type""",
                        (week_dates[0], week_dates[-1])).fetchall()
    db.close()
    return render_template('vendor/menu.html', hostels=hostels, week_dates=week_dates,
                           menus=menus, today=today)

@vendor_bp.route('/complaints')
@vendor_required
def complaints():
    db    = get_db()
    status_f = request.args.get('status','open')
    comps = db.execute("""
        SELECT fc.*, s.name, s.usn, h.name as hostel_name
        FROM food_complaints fc
        JOIN students s ON s.id=fc.student_id
        JOIN hostels h ON h.id=fc.hostel_id
        WHERE fc.status=?
        ORDER BY fc.submitted_at DESC
    """, (status_f,)).fetchall()
    db.close()
    return render_template('vendor/complaints.html', complaints=comps, status_filter=status_f)

@vendor_bp.route('/menu/save', methods=['POST'])
@vendor_required
def save_menu():
    """Handles menu save form from menu template (posts date + per-hostel meal items)."""
    menu_date = request.form.get('date', date.today().isoformat())
    db = get_db()
    hostels = db.execute("SELECT * FROM hostels ORDER BY code").fetchall()
    for h in hostels:
        code = h['code'].lower()  # 'b' or 'g'
        for meal in ('breakfast','lunch','dinner'):
            veg_items = request.form.get(f'{code}_{meal}_veg','').strip()
            nv_items  = request.form.get(f'{code}_{meal}_nv','').strip()
            if veg_items:
                db.execute("""INSERT INTO weekly_menus(hostel_id,menu_date,meal_type,veg_items,non_veg_items,uploaded_by)
                              VALUES(?,?,?,?,?,?)
                              ON CONFLICT(hostel_id,menu_date,meal_type) DO UPDATE SET
                              veg_items=excluded.veg_items, non_veg_items=excluded.non_veg_items""",
                           (h['id'], menu_date, meal, veg_items, nv_items, session['user_id']))
    db.commit()
    db.close()
    flash('Menu saved successfully', 'success')
    return redirect(url_for('vendor.menu'))

@vendor_bp.route('/complaints/<int:cid>/respond', methods=['POST'])
@vendor_required
def respond_complaint(cid):
    db   = get_db()
    resp = request.form.get('response','').strip()
    new_status = request.form.get('new_status','acknowledged')
    db.execute("""UPDATE food_complaints SET vendor_response=?, status=?,
                  resolved_at=CASE WHEN ? IN ('resolved') THEN datetime('now') ELSE resolved_at END
                  WHERE id=?""", (resp, new_status, new_status, cid))
    db.commit()
    db.close()
    flash('Response saved', 'success')
    return redirect(url_for('vendor.complaints'))
