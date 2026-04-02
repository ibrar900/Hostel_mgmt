from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

def get_db():
    conn = sqlite3.connect(current_app.config["DB_PATH"], timeout=30)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip().lower()
        password = request.form.get('password','')
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id']   = user['id']
            session['role']      = user['role']
            session['full_name'] = user['full_name']
            session['username']  = user['username']
            # get hostel_id for wardens
            if user['role'] == 'warden_boys':
                h = db.execute("SELECT id FROM hostels WHERE code='B'").fetchone()
                session['hostel_id'] = h['id']
            elif user['role'] == 'warden_girls':
                h = db.execute("SELECT id FROM hostels WHERE code='G'").fetchone()
                session['hostel_id'] = h['id']
            elif user['role'] == 'office':
                pass  # no hostel scoping for office
            elif user['role'] == 'student':
                st = db.execute("SELECT id FROM students WHERE user_id=?", (user['id'],)).fetchone()
                if st:
                    session['student_id'] = st['id']
                    ra = db.execute("""SELECT r.hostel_id FROM room_allotments ra
                                       JOIN rooms r ON r.id=ra.room_id
                                       WHERE ra.student_id=? AND ra.is_current=1""", (st['id'],)).fetchone()
                    if ra: session['hostel_id'] = ra['hostel_id']
            db.close()
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
        db.close()
    return render_template('auth/login.html')

@auth_bp.route('/logout', methods=['GET','POST'])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['GET','POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        cur  = request.form.get('current_password','')
        new  = request.form.get('new_password','')
        conf = request.form.get('confirm_password','')
        if new != conf:
            flash('New passwords do not match', 'error')
        else:
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
            if user and check_password_hash(user['password_hash'], cur):
                db.execute("UPDATE users SET password_hash=? WHERE id=?",
                           (generate_password_hash(new), session['user_id']))
                db.commit()
                flash('Password changed successfully', 'success')
            else:
                flash('Current password is incorrect', 'error')
            db.close()
    return render_template('auth/change_password.html')
