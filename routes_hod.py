from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Branch, Subject, Division, Exam, Notification
from app.services.academic_calendar_service import (
    build_branch_calendar,
    build_calendar_api_payload,
    create_branch_exam,
    create_calendar_event as create_calendar_event_record,
    delete_calendar_event as delete_calendar_event_record,
    get_branch_calendar_event,
    parse_calendar_date,
    update_calendar_event as update_calendar_event_record,
)
from app.services.hod_analytics import build_branch_result_analytics, generate_branch_result_insights
from app.utils import role_required

hod_bp = Blueprint('hod', __name__)

@hod_bp.before_request
@login_required
@role_required('hod')
def check_hod():
    pass

@hod_bp.route('/')
def dashboard():
    pending_users = User.query.filter(User.role.in_(['faculty', 'student']), User.branch_id == current_user.branch_id, User.verified == False).all()
    subjects = Subject.query.filter_by(branch_id=current_user.branch_id).count()
    divisions = Division.query.filter_by(branch_id=current_user.branch_id).count()
    
    return render_template('hod/dashboard.html', 
                           pending_users=pending_users, 
                           stats={'subjects': subjects, 'divisions': divisions})


def _calendar_redirect_args(semester, month, year, edit_event_id=None):
    args = {'semester': semester, 'month': month, 'year': year}
    if edit_event_id:
        args['edit_event_id'] = edit_event_id
    return args


def _render_hod_calendar():
    selected_semester = request.args.get('semester', type=int)
    selected_month = request.args.get('month', type=int)
    selected_year = request.args.get('year', type=int)
    edit_event_id = request.args.get('edit_event_id', type=int)

    calendar_data = build_branch_calendar(
        current_user.branch_id,
        semester=selected_semester,
        month=selected_month,
        year=selected_year,
        user=current_user,
    )
    subjects_list = Subject.query.filter_by(branch_id=current_user.branch_id).order_by(Subject.semester.asc(), Subject.name.asc()).all()

    edit_event = None
    if edit_event_id:
        try:
            edit_event = get_branch_calendar_event(current_user.branch_id, edit_event_id)
        except ValueError:
            flash("Calendar event not found for your branch.", "danger")

    return render_template(
        'calendar/calendar.html',
        calendar_data=calendar_data,
        can_manage=True,
        subjects=subjects_list,
        edit_event=edit_event,
        back_endpoint='hod.dashboard',
        calendar_endpoint='hod.academic_calendar',
        create_endpoint='hod.create_calendar_event',
        update_endpoint='hod.update_calendar_event',
        delete_endpoint='hod.delete_calendar_event',
        page_title='Academic Calendar',
        page_heading='Manage branch and semester calendars with a clean monthly view.',
        page_description='Create, update, and remove semester-specific academic events for your branch without affecting other branches or semesters.',
    )


@hod_bp.route('/academic-calendar')
def academic_calendar():
    return _render_hod_calendar()


@hod_bp.route('/api/academic-calendar')
def calendar_api():
    return jsonify(
        build_calendar_api_payload(
            current_user.branch_id,
            semester=request.args.get('semester', type=int),
            month=request.args.get('month', type=int),
            year=request.args.get('year', type=int),
            user=current_user,
        )
    )


@hod_bp.route('/academic-calendar/events', methods=['POST'])
def create_calendar_event():
    title = (request.form.get('title') or '').strip()
    date_raw = request.form.get('date')
    event_type = request.form.get('type')
    semester = request.form.get('semester', type=int)
    description = (request.form.get('description') or '').strip() or None
    selected_month = request.form.get('month', type=int)
    selected_year = request.form.get('year', type=int)

    if not title or not date_raw or not event_type or not semester:
        flash("Title, date, type, and semester are required for calendar events.", "danger")
        return redirect(url_for('hod.academic_calendar', **_calendar_redirect_args(semester or 1, selected_month, selected_year)))

    try:
        event_date = parse_calendar_date(date_raw)
        create_calendar_event_record(current_user.branch_id, semester, title, event_date, event_type, description=description)
        flash(f"{event_type.title()} added to the semester calendar.", "success")
    except ValueError as error:
        flash(str(error), "danger")
    return redirect(url_for('hod.academic_calendar', **_calendar_redirect_args(semester, selected_month, selected_year)))


@hod_bp.route('/academic-calendar/events/<int:event_id>/update', methods=['POST'])
def update_calendar_event(event_id):
    title = (request.form.get('title') or '').strip()
    date_raw = request.form.get('date')
    event_type = request.form.get('type')
    semester = request.form.get('semester', type=int)
    description = (request.form.get('description') or '').strip() or None
    selected_month = request.form.get('month', type=int)
    selected_year = request.form.get('year', type=int)

    if not title or not date_raw or not event_type or not semester:
        flash("Title, date, type, and semester are required for calendar events.", "danger")
        return redirect(url_for('hod.academic_calendar', **_calendar_redirect_args(semester or 1, selected_month, selected_year, edit_event_id=event_id)))

    try:
        event_date = parse_calendar_date(date_raw)
        update_calendar_event_record(current_user.branch_id, event_id, semester, title, event_date, event_type, description=description)
        flash("Calendar event updated successfully.", "success")
    except ValueError as error:
        flash(str(error), "danger")
        return redirect(url_for('hod.academic_calendar', **_calendar_redirect_args(semester, selected_month, selected_year, edit_event_id=event_id)))
    return redirect(url_for('hod.academic_calendar', **_calendar_redirect_args(semester, selected_month, selected_year)))


@hod_bp.route('/academic-calendar/events/<int:event_id>/delete', methods=['POST'])
def delete_calendar_event(event_id):
    semester = request.form.get('semester', type=int)
    selected_month = request.form.get('month', type=int)
    selected_year = request.form.get('year', type=int)

    try:
        delete_calendar_event_record(current_user.branch_id, event_id)
        flash("Calendar event deleted successfully.", "success")
    except ValueError as error:
        flash(str(error), "danger")
    return redirect(url_for('hod.academic_calendar', **_calendar_redirect_args(semester or 1, selected_month, selected_year)))


@hod_bp.route('/result-analytics')
def result_analytics():
    analytics = build_branch_result_analytics(current_user.branch_id)
    return render_template(
        'hod/result_analytics.html',
        analytics_summary=analytics['summary'],
        analytics_insights=generate_branch_result_insights(analytics),
        weak_subjects=analytics['weak_subjects'],
        top_performers=analytics['top_performers'],
    )


@hod_bp.route('/api/result-analytics/overview')
def result_analytics_overview_api():
    analytics = build_branch_result_analytics(current_user.branch_id)
    return jsonify(
        {
            'summary': analytics['summary'],
            'subject_averages': analytics['subject_averages'],
            'weak_subjects': analytics['weak_subjects'],
            'top_performers': analytics['top_performers'],
            'insights': generate_branch_result_insights(analytics),
        }
    )


@hod_bp.route('/api/result-analytics/trends')
def result_analytics_trends_api():
    analytics = build_branch_result_analytics(current_user.branch_id)
    return jsonify({'performance_trends': analytics['performance_trends']})

@hod_bp.route('/verify/<int:user_id>', methods=['POST'])
def verify_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.branch_id == current_user.branch_id:
        user.verified = True
        db.session.commit()
        flash(f"{user.role.capitalize()} {user.first_name} {user.last_name} has been verified.", "success")
    return redirect(url_for('hod.dashboard'))

@hod_bp.route('/subjects', methods=['GET', 'POST'])
def subjects():
    if request.method == 'POST':
        name = request.form.get('name')
        semester = request.form.get('semester')
        new_subject = Subject(name=name, branch_id=current_user.branch_id, semester=int(semester))
        db.session.add(new_subject)
        db.session.commit()
        flash(f"Subject {name} created.", "success")
        return redirect(url_for('hod.subjects'))
    
    subjects_list = Subject.query.filter_by(branch_id=current_user.branch_id).all()
    return render_template('hod/subjects.html', subjects=subjects_list)

@hod_bp.route('/divisions', methods=['GET', 'POST'])
def divisions():
    if request.method == 'POST':
        name = request.form.get('name')
        new_division = Division(name=name, branch_id=current_user.branch_id)
        db.session.add(new_division)
        db.session.commit()
        flash(f"Division {name} created.", "success")
        return redirect(url_for('hod.divisions'))
    
    divisions_list = Division.query.filter_by(branch_id=current_user.branch_id).all()
    return render_template('hod/divisions.html', divisions=divisions_list)

@hod_bp.route('/exams', methods=['GET', 'POST'])
def exams():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        subject_id = request.form.get('subject_id', type=int)
        date_raw = request.form.get('date')
        max_marks = (request.form.get('max_marks') or '').strip()

        if not name or not subject_id or not date_raw or not max_marks:
            flash("Exam name, subject, date, and max marks are required.", "danger")
            return redirect(url_for('hod.exams'))

        try:
            exam_date = parse_calendar_date(date_raw)
            create_branch_exam(current_user.branch_id, name, subject_id, exam_date, max_marks)
            flash(f"Exam {name} created.", "success")
        except ValueError as error:
            flash(str(error), "danger")
        return redirect(url_for('hod.exams'))
        
    exams_list = Exam.query.join(Subject).filter(Subject.branch_id == current_user.branch_id).all()
    subjects_list = Subject.query.filter_by(branch_id=current_user.branch_id).all()
    return render_template('hod/exams.html', exams=exams_list, subjects=subjects_list)

@hod_bp.route('/release_results/<int:exam_id>', methods=['POST'])
def release_results(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    exam.results_released = not exam.results_released
    db.session.commit()
    status = "Released" if exam.results_released else "Hidden"
    flash(f"Results for {exam.name} are now {status}.", "info")
    return redirect(url_for('hod.exams'))

@hod_bp.route('/assign_faculty', methods=['GET', 'POST'])
def assign_faculty():
    if request.method == 'POST':
        faculty_id = request.form.get('faculty_id')
        subject_id = request.form.get('subject_id')
        
        faculty = User.query.get(faculty_id)
        subject = Subject.query.get(subject_id)
        
        if subject not in faculty.subjects_taught:
            faculty.subjects_taught.append(subject)
            db.session.commit()
            flash("Faculty assigned to subject successfully.", "success")
            
        return redirect(url_for('hod.assign_faculty'))

    faculty_list = User.query.filter_by(role='faculty', branch_id=current_user.branch_id, verified=True).all()
    subjects_list = Subject.query.filter_by(branch_id=current_user.branch_id).all()
    return render_template('hod/assign_faculty.html', faculty=faculty_list, subjects=subjects_list)

@hod_bp.route('/notify', methods=['GET', 'POST'])
def send_notification():
    if request.method == 'POST':
        message = request.form.get('message')
        target = request.form.get('target_role')
        
        notif = Notification(message=message, target_role=target, branch_id=current_user.branch_id)
        db.session.add(notif)
        db.session.commit()
        flash("Notification sent.", "success")
        return redirect(url_for('hod.send_notification'))
        
    notifs = Notification.query.filter_by(branch_id=current_user.branch_id).order_by(Notification.created_at.desc()).all()
    return render_template('hod/notify.html', notifications=notifs)
