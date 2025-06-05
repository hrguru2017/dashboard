# wsgi.py
from app import create_app # Import your create_app function from app.py

application = create_app() # Call create_app to get the Flask instance, and name it 'application'