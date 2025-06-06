# daily_submission_dashboard/app.py

import os
from flask import Flask
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect # <-- 1. IMPORT CSRFProtect

# Import extensions from extensions.py
from extensions import db, login_manager
# Import User model for user_loader
from models import User 

load_dotenv() 

csrf = CSRFProtect() # <-- 2. CREATE AN INSTANCE GLOBALLY

def create_app():
    print(f"APP.PY (create_app): Creating Flask app. PID: {os.getpid()}")
    app = Flask(__name__, instance_relative_config=True)

    # --- Configuration ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_default_secret_key_CHANGE_THIS_IMMEDIATELY')
    
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        app.logger.warning(f"Could not create instance folder at {app.instance_path}: {e}")
    
    # Use DATABASE_URL environment variable for production, fallback to SQLite for local development
    # This pattern allows you to develop with SQLite locally and deploy with Postgres easily
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(app.instance_path, "submissions.sqlite")}' # Fallback for local development
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Keep this

    
    app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError as e:
        app.logger.error(f"Could not create upload folder at {app.config['UPLOAD_FOLDER']}: {e}")

    # --- Initialize Extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app) # <-- 3. INITIALIZE CSRFProtect WITH THE APP
    print(f"APP.PY (create_app): Extensions initialized (including CSRF). PID: {os.getpid()}")

    # --- Flask-Login Configuration ---
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.login_view = 'auth.login' 
    login_manager.login_message_category = 'info'

    # --- Register Blueprints ---
    from auth import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    from main import main_bp
    app.register_blueprint(main_bp, url_prefix='/')
    print(f"APP.PY (create_app): Blueprints registered. PID: {os.getpid()}")

    # --- Create Database Tables ---
    with app.app_context():
        db.create_all()
        print(f"APP.PY (create_app): Database tables ensured/created at {db_path}. PID: {os.getpid()}")

    print(f"APP.PY (create_app): App creation complete. Returning app instance {id(app)}. PID: {os.getpid()}")
    return app

if __name__ == '__main__':
    print(f"APP.PY (__main__): Starting application development server. PID: {os.getpid()}")
    app_instance = create_app()
    if not os.path.isdir(app_instance.config['UPLOAD_FOLDER']):
        try:
            os.makedirs(app_instance.config['UPLOAD_FOLDER'], exist_ok=True) # use exist_ok=True for robustness
            print(f"INFO: Upload folder '{app_instance.config['UPLOAD_FOLDER']}' created successfully.")
        except OSError as e:
            print(f"ERROR: Could not create upload folder '{app_instance.config['UPLOAD_FOLDER']}': {e}")

    # Run the development server
    app_instance.run(debug=True, port=5000) # Added port for clarity, can be omitted
