# daily_submission_dashboard/forms.py

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField, TextAreaField # Added TextAreaField
from wtforms.fields import DateField 
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError, EqualTo, Optional
from datetime import date, datetime
from models import User # For UserCreationForm's username validation

# --- LOGIN FORM ---
class LoginForm(FlaskForm):
    username = StringField('Username', 
                           validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', 
                             validators=[DataRequired(), Length(min=6, max=120)])
    submit = SubmitField('Login')

# --- CUSTOM VALIDATORS FOR SUBMISSIONFORM DATE ---
def not_future_date(form, field):
    if field.data and field.data > date.today():
        raise ValidationError('Submission date cannot be in the future.')

def current_month_only(form, field):
    if field.data:
        today = date.today()
        if field.data.year != today.year or field.data.month != today.month:
            raise ValidationError('Submissions can only be added for the current month.')

# --- SUBMISSION FORM (Now for File Upload) ---
class SubmissionForm(FlaskForm):
    submission_date = DateField('Submission Date for Profiles', 
                                format='%Y-%m-%d', 
                                default=date.today,
                                validators=[DataRequired(), not_future_date, current_month_only])
    
    profile_sheet = FileField('Profile Excel Sheet (.xlsx)', 
                              validators=[
                                  FileRequired(message="Please select an Excel file."),
                                  FileAllowed(['xlsx'], 'XLSX Excel files only!')
                              ])
    
    submit = SubmitField('Upload Profile Sheet')

# --- MONTH/YEAR SELECTION FORM (for Monthly Report) ---
class MonthYearSelectionForm(FlaskForm):
    current_year = datetime.now().year
    year = IntegerField('Year', 
                        validators=[DataRequired(), NumberRange(min=2020, max=current_year + 5)],
                        default=current_year)
    month = SelectField('Month', 
                        choices=[
                            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
                            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
                            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
                        ],
                        coerce=int, 
                        validators=[DataRequired()],
                        default=datetime.now().month
                       )
    submit = SubmitField('Generate Report')

# --- USER CREATION FORM ---
class UserCreationForm(FlaskForm):
    username = StringField('Username', 
                           validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', 
                             validators=[DataRequired(), Length(min=6, max=120)])
    confirm_password = PasswordField('Confirm Password', 
                                     validators=[DataRequired(), EqualTo('password', message='Passwords must match.')])
    role = SelectField('Role', 
                       choices=[('member', 'Member'), ('manager', 'Manager')],
                       validators=[DataRequired()])
    submit = SubmitField('Create User')

    # Custom validator to check if username already exists
    def validate_username(self, username_field):
        user = User.query.filter_by(username=username_field.data).first()
        if user:
            raise ValidationError('That username is already taken. Please choose a different one.')

# --- EDIT PROFILE FORM (Includes new Feedback field) ---
class EditProfileForm(FlaskForm):
    profile_activity_date = DateField('Activity Date', format='%Y-%m-%d', validators=[Optional()])
    position = StringField('Position', validators=[Optional(), Length(max=255)])
    client = StringField('Client', validators=[Optional(), Length(max=255)])
    candidate_name = StringField('Candidate Name', validators=[DataRequired(), Length(max=255)])
    contact_number = StringField('Contact Number', validators=[Optional(), Length(max=50)])
    email_id = StringField('Email ID', validators=[Optional(), Length(max=255)]) # Consider adding Email() validator
    total_experience = StringField('Total Experience', validators=[Optional(), Length(max=100)])
    current_ctc = StringField('Current CTC', validators=[Optional(), Length(max=100)])
    expected_ctc = StringField('Expected CTC', validators=[Optional(), Length(max=100)])
    notice_period = StringField('Notice Period', validators=[Optional(), Length(max=100)])
    feedback = TextAreaField('Feedback', validators=[Optional()]) # <-- NEW FIELD ADDED HERE
    submit = SubmitField('Update Profile')