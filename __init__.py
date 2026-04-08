import os

from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from sqlalchemy import inspect, text
from app.config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


def _build_nav_items(role):
    nav_map = {
        'admin': [
            {'label': 'Overview', 'endpoint': 'admin.dashboard', 'icon': 'dashboard'},
            {'label': 'Branches', 'endpoint': 'admin.manage_branches', 'icon': 'branches'},
        ],
        'hod': [
            {'label': 'Overview', 'endpoint': 'hod.dashboard', 'icon': 'dashboard'},
            {'label': 'Calendar', 'endpoint': 'hod.academic_calendar', 'icon': 'calendar'},
            {'label': 'Analytics', 'endpoint': 'hod.result_analytics', 'icon': 'analytics'},
            {'label': 'Subjects', 'endpoint': 'hod.subjects', 'icon': 'subjects'},
            {'label': 'Divisions', 'endpoint': 'hod.divisions', 'icon': 'divisions'},
            {'label': 'Exams', 'endpoint': 'hod.exams', 'icon': 'exams'},
            {'label': 'Faculty', 'endpoint': 'hod.assign_faculty', 'icon': 'faculty'},
            {'label': 'Announcements', 'endpoint': 'hod.send_notification', 'icon': 'notifications'},
        ],
        'faculty': [
            {'label': 'Overview', 'endpoint': 'faculty.dashboard', 'icon': 'dashboard'},
            {'label': 'Calendar', 'endpoint': 'faculty.calendar', 'icon': 'calendar'},
            {'label': 'Assignments', 'endpoint': 'faculty.assignments', 'icon': 'assignments'},
            {'label': 'Leaves', 'endpoint': 'faculty.leave_requests', 'icon': 'leave'},
        ],
        'student': [
            {'label': 'Overview', 'endpoint': 'student.dashboard', 'icon': 'dashboard'},
            {'label': 'Calendar', 'endpoint': 'student.calendar', 'icon': 'calendar'},
            {'label': 'Assignments', 'endpoint': 'student.assignments', 'icon': 'assignments'},
            {'label': 'Leaves', 'endpoint': 'student.leave_requests', 'icon': 'leave'},
            {'label': 'Performance', 'endpoint': 'student.performance_dashboard', 'icon': 'performance'},
            {'label': 'Attendance', 'endpoint': 'student.attendance', 'icon': 'attendance'},
            {'label': 'Results', 'endpoint': 'student.results', 'icon': 'results'},
            {'label': 'Timetable', 'endpoint': 'student.timetable', 'icon': 'timetable'},
            {'label': 'Reports', 'endpoint': 'student.reports_home', 'icon': 'reports'},
        ],
    }
    return nav_map.get(role, [])


def _ensure_calendar_event_schema():
    inspector = inspect(db.engine)
    if 'calendar_event' not in inspector.get_table_names():
        return

    column_names = {column['name'] for column in inspector.get_columns('calendar_event')}
    with db.engine.begin() as connection:
        if 'semester' not in column_names:
            connection.execute(text("ALTER TABLE calendar_event ADD COLUMN semester INTEGER NOT NULL DEFAULT 1"))
        if 'description' not in column_names:
            connection.execute(text("ALTER TABLE calendar_event ADD COLUMN description TEXT"))

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config['ASSIGNMENT_UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from app import models  # register models
        db.create_all()         # create tables
        _ensure_calendar_event_schema()

    from app.auth import auth_bp
    from app.routes_admin import admin_bp
    from app.routes_hod import hod_bp
    from app.routes_faculty import faculty_bp
    from app.routes_student import student_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(hod_bp, url_prefix='/hod')
    app.register_blueprint(faculty_bp, url_prefix='/faculty')
    app.register_blueprint(student_bp, url_prefix='/student')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_shell_data():
        alerts = []
        nav_items = []
        branch_name = "Platform Workspace"

        if current_user.is_authenticated:
            from sqlalchemy import or_
            from app.models import Notification

            nav_items = _build_nav_items(current_user.role)
            if current_user.branch_ref:
                branch_name = current_user.branch_ref.name
            elif current_user.role == 'admin':
                branch_name = "Global Administration"

            if current_user.role in ('student', 'faculty'):
                notifications = Notification.query.filter(
                    Notification.target_role.in_(['all', current_user.role]),
                    or_(
                        Notification.branch_id == current_user.branch_id,
                        Notification.branch_id.is_(None),
                    ),
                ).order_by(Notification.created_at.desc()).limit(6).all()
            elif current_user.role == 'hod':
                notifications = Notification.query.filter_by(
                    branch_id=current_user.branch_id
                ).order_by(Notification.created_at.desc()).limit(6).all()
            else:
                notifications = []

            alerts = [
                {
                    'message': notification.message,
                    'meta': notification.created_at.strftime('%d %b %Y, %I:%M %p'),
                    'tag': (
                        'Branch Update'
                        if notification.target_role == 'all'
                        else f"{notification.target_role.capitalize()} Update"
                    ),
                }
                for notification in notifications
            ]

        return {
            'shell_nav_items': nav_items,
            'shell_alerts': alerts,
            'shell_alert_count': len(alerts),
            'shell_branch_name': branch_name,
        }

    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    return User.query.get(int(user_id))
