# daily_submission_dashboard/auth.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user as flask_login_current_user

from models import User # Import User model
from extensions import db
from forms import LoginForm # Import your LoginForm

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already authenticated, redirect them to the dashboard
    if flask_login_current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm() # Instantiate the login form

    # Handle POST request (when form is submitted)
    if form.validate_on_submit():
        username_from_form = form.username.data
        password_from_form = form.password.data
        
        # Attempt to find the user in the database
        user = User.query.filter_by(username=username_from_form).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(password_from_form):
            login_user(user) # Log in the user with Flask-Login
            
            # Success flash message (optional - commented out as per discussion)
            # If you want a success message, you can uncomment the line below.
            # flash(f'Logged in successfully as {user.username}!', 'success') 
            
            # Redirect to the 'next' page if it was provided (e.g., by @login_required)
            # Otherwise, redirect to the main dashboard.
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            # If login is unsuccessful, flash an error message
            flash('Login Unsuccessful. Please check username and password.', 'danger')
            
    # For GET request or if form validation fails, render the login template
    # Pass the form object to the template so it can be displayed
    return render_template('login.html', title='Sign In', form=form)

@auth_bp.route('/logout')
@login_required # Ensures only logged-in users can access the logout route
def logout():
    logout_user() # Log out the user with Flask-Login
    flash('You have been logged out.', 'info') # Flash a confirmation message
    return redirect(url_for('auth.login')) # Redirect to the login page after logout