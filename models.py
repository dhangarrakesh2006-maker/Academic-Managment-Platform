from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

faculty_subject = db.Table('faculty_subject',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)

student_subject = db.Table('student_subject',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subject.id'), primary_key=True)
)

local_guardian = db.Table('local_guardian',
    db.Column('faculty_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    divisions = db.relationship('Division', backref='branch', lazy=True)
    subjects = db.relationship('Subject', backref='branch', lazy=True)
    users = db.relationship('User', backref='branch_ref', lazy=True)
    calendar_events = db.relationship('CalendarEvent', backref='branch', lazy=True, cascade='all, delete-orphan')

class Division(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(10), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    users = db.relationship('User', backref='division_ref', lazy=True)
    __table_args__ = (db.UniqueConstraint('name', 'branch_id', name='_branch_div_uc'),)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    semester = db.Column(db.Integer, nullable=False, default=1)
    exams = db.relationship('Exam', backref='subject', lazy=True)
    attendances = db.relationship('Attendance', backref='subject', lazy=True)
    assignments = db.relationship('Assignment', backref='subject', lazy=True, cascade='all, delete-orphan')

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    verified = db.Column(db.Boolean, default=False)

    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=True)
    division_id = db.Column(db.Integer, db.ForeignKey('division.id'), nullable=True)
    
    prn = db.Column(db.String(20), unique=True, nullable=True)
    roll_no = db.Column(db.Integer, nullable=True)

    subjects_taught = db.relationship('Subject', secondary=faculty_subject, lazy='subquery', backref=db.backref('taught_by', lazy=True))
    subjects_enrolled = db.relationship('Subject', secondary=student_subject, lazy='subquery', backref=db.backref('enrolled_students', lazy=True))
    local_guardian_students = db.relationship(
        'User',
        secondary=local_guardian,
        primaryjoin=id == local_guardian.c.faculty_id,
        secondaryjoin=id == local_guardian.c.student_id,
        lazy='subquery',
        backref=db.backref('local_guardians', lazy='subquery'),
    )

    attendances = db.relationship('Attendance', backref='student', lazy=True)
    marks = db.relationship('Marks', backref='student', lazy=True)
    assignments_created = db.relationship('Assignment', backref='faculty', lazy=True, foreign_keys='Assignment.faculty_id')
    submissions = db.relationship('Submission', backref='student', lazy=True, cascade='all, delete-orphan')
    leave_requests = db.relationship(
        'LeaveRequest',
        backref='student',
        lazy=True,
        cascade='all, delete-orphan',
        foreign_keys='LeaveRequest.student_id',
    )
    reviewed_leave_requests = db.relationship(
        'LeaveRequest',
        backref='reviewer',
        lazy=True,
        foreign_keys='LeaveRequest.reviewed_by_id',
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint('student_id', 'subject_id', 'date', name='_student_subject_date_uc'),)

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    max_marks = db.Column(db.Float, nullable=False)
    results_released = db.Column(db.Boolean, default=False)
    marks = db.relationship('Marks', backref='exam', lazy=True)

class Marks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False)
    __table_args__ = (db.UniqueConstraint('student_id', 'exam_id', name='_student_exam_uc'),)

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey('division.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day_of_week = db.Column(db.String(15), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    branch = db.relationship('Branch', backref=db.backref('timetable_slots', lazy=True))
    division = db.relationship('Division', backref=db.backref('timetable_slots', lazy=True))
    subject = db.relationship('Subject', backref=db.backref('timetable_slots', lazy=True))
    faculty = db.relationship('User', foreign_keys=[faculty_id], backref=db.backref('timetable_slots', lazy=True))

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    due_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submissions = db.relationship('Submission', backref='assignment', lazy=True, cascade='all, delete-orphan')

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignment.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submission_text = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(255), nullable=True)
    original_file_name = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    grade = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_at = db.Column(db.DateTime, nullable=True)
    __table_args__ = (db.UniqueConstraint('assignment_id', 'student_id', name='_assignment_student_uc'),)

class LeaveRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class CalendarEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    semester = db.Column(db.Integer, nullable=False, default=1)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    target_role = db.Column(db.String(20), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
