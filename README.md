# Hostel_mgmt

A Flask-based Hostel Management System designed to manage hostel-related operations through role-based access for students, wardens, vendors, office staff, and chairman users. [Based on project structure]

## Project overview

This project provides a centralized hostel management platform built with Flask. The application uses multiple blueprints to separate modules for authentication and role-specific dashboards, making the system modular and easier to maintain.

### Main modules

- **Authentication**: Handles login and session-based access control.
- **Warden module**: Separate dashboard for hostel wardens.
- **Student module**: Student dashboard with access to complaints, movement, circulars, attendance, food, protocols, and permissions.
- **Vendor module**: Vendor-specific operations.
- **Chairman module**: Chairman dashboard and reports.
- **Office module**: Office dashboard for student records, fees, circulars, and administration.

## Tech stack

- Python
- Flask 3.0.0
- Werkzeug 3.0.1
- Gunicorn 21.2.0

## Project structure

```bash
Hostel_mgmt/
├── app.py
├── wsgi.py
├── requirements.txt
├── app.log
├── blueprints/
├── database/
├── uploads/
├── templates/
├── static/
```

## How it works

The application starts through `app.py`, creates the Flask app, sets the database and upload paths, and registers all blueprints. Based on the logged-in user's role, it redirects users to the correct dashboard.

Configured roles include:

- `warden_boys`
- `warden_girls`
- `student`
- `vendor`
- `chairman`
- `office`

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ibrar900/Hostel_mgmt.git
cd Hostel_mgmt
```

### 2. Create a virtual environment

#### On Linux / macOS
```bash
python3 -m venv venv
source venv/bin/activate
```

#### On Windows
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Run the project

### Development mode

```bash
python app.py
```

The Flask development server runs on:

```bash
http://127.0.0.1:5050
```

### Production mode

You can use Gunicorn with the WSGI entry point:

```bash
gunicorn wsgi:application
```

## Features observed from the application flow

From the available app logs and routing setup, the system includes or routes to the following areas:

### Student
- Dashboard
- Complaints
- Movement
- Circulars
- Attendance
- Food
- Protocols
- Permissions

### Office
- Dashboard
- Student management
- Fees
- Circulars

### Chairman
- Reports

### Warden
- Dashboard
- Reports

## Error handling

The application includes a custom 404 error handler that renders an error page when a route is not found.

## Notes

- The app currently uses a Flask secret key configured directly in code.
- The database path is configured as `database/hostel.db`.
- Uploaded files are stored in the `uploads` directory.
- The development server should not be used in production.

## Future improvements

- Move secret keys and configuration to environment variables.
- Add a `.env` file and configuration class.
- Add database migration support.
- Improve deployment setup for production.
- Add screenshots and sample credentials for demonstration.

## License

Add your preferred license here.
