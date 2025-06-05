# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

print(f"EXTENSIONS.PY: Initializing db and login_manager. PID: {os.getpid()}")
db = SQLAlchemy()
login_manager = LoginManager()
print(f"EXTENSIONS.PY: db instance {id(db)}, login_manager instance {id(login_manager)}. PID: {os.getpid()}")