"""
WSGI entry point for HKBK Hostel Management System (Production)
"""
from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run()
