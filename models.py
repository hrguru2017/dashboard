# daily_submission_dashboard/models.py

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime 
from extensions import db

# ... (User model and SubmissionBatch model remain the same) ...
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='member')
    submission_batches = db.relationship('SubmissionBatch', backref='submitter', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    def __repr__(self):
        return f'<User {self.username}>'

class SubmissionBatch(db.Model):
    __tablename__ = 'submission_batches'
    id = db.Column(db.Integer, primary_key=True)
    submission_date = db.Column(db.Date, nullable=False, default=date.today)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_filename = db.Column(db.String(255), nullable=True)
    processed_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    number_of_profiles = db.Column(db.Integer, nullable=False, default=0)
    profiles = db.relationship('Profile', backref='batch', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<SubmissionBatch ID {self.id} by User ID {self.user_id} on {self.submission_date.strftime("%Y-%m-%d")} containing {self.number_of_profiles} profiles>'


class Profile(db.Model):
    __tablename__ = 'profiles'
    id = db.Column(db.Integer, primary_key=True)
    submission_batch_id = db.Column(db.Integer, db.ForeignKey('submission_batches.id'), nullable=False)

    profile_activity_date = db.Column(db.Date, nullable=True) 
    position = db.Column(db.String(255), nullable=True)
    client = db.Column(db.String(255), nullable=True)
    candidate_name = db.Column(db.String(255), nullable=True)
    contact_number = db.Column(db.String(50), nullable=True) 
    email_id = db.Column(db.String(255), nullable=True)
    total_experience = db.Column(db.String(100), nullable=True) 
    current_ctc = db.Column(db.String(100), nullable=True)    
    expected_ctc = db.Column(db.String(100), nullable=True)   
    notice_period = db.Column(db.String(100), nullable=True)      
    feedback = db.Column(db.Text, nullable=True)  # <-- NEW FIELD ADDED HERE

    def __repr__(self):
        return f'<Profile ID {self.id} Name: {self.candidate_name} for Batch ID {self.submission_batch_id}>'