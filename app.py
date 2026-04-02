from flask import Flask, render_template, redirect, url_for, session
from blueprints.auth import auth_bp
from blueprints.warden import warden_bp
from blueprints.student import student_bp
from blueprints.vendor import vendor_bp
from blueprints.chairman import chairman_bp
from blueprints.office import office_bp
import os

def create_app():
    app = Flask(__name__)
    app.secret_key = 'hkbk_hostel_secret_2026'
    app.config['DB_PATH'] = os.path.join(os.path.dirname(__file__), 'database', 'hostel.db')
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')

    app.register_blueprint(auth_bp)
    app.register_blueprint(warden_bp,   url_prefix='/warden')
    app.register_blueprint(student_bp,  url_prefix='/student')
    app.register_blueprint(vendor_bp,   url_prefix='/vendor')
    app.register_blueprint(chairman_bp, url_prefix='/chairman')
    app.register_blueprint(office_bp,  url_prefix='/office')

    @app.route('/')
    def index():
        if 'user_id' not in session:
            return render_template('index.html')
        role = session.get('role')
        if role in ('warden_boys','warden_girls'): return redirect(url_for('warden.dashboard'))
        if role == 'student':    return redirect(url_for('student.dashboard'))
        if role == 'vendor':     return redirect(url_for('vendor.dashboard'))
        if role == 'chairman':   return redirect(url_for('chairman.dashboard'))
        if role == 'office':     return redirect(url_for('office.dashboard'))
        return redirect(url_for('auth.login'))

    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404, msg='Page not found'), 404

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5050)
