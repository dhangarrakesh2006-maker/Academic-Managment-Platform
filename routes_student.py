from datetime import datetime

from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.models import Assignment, Attendance, LeaveRequest, Notification, Submission, Subject
from app.services.academic_calendar_service import build_branch_calendar, build_calendar_api_payload
from app.services.assignment_service import (
    build_assignment_card,
    build_student_assignment_cards,
    can_student_access_assignment,
    get_submission_for_student,
    save_submission_file,
)
from app.services.leave_service import (
    build_student_leave_cards,
    can_student_apply_leave,
    get_student_guardians,
    parse_leave_date,
)
from app.services.student_analytics import (
    build_monthly_attendance_report,
    build_performance_history,
    build_reports_overview,
    build_remarks_report,
    build_semester_result_report,
    build_subject_performance,
    generate_performance_insights,
    get_month_options,
)
from app.utils import get_low_attendance_risk, predict_student_performance, role_required

student_bp = Blueprint('student', __name__)


@student_bp.before_request
@login_required
@role_required('student')
def check_student():
    pass


@student_bp.route('/')
def dashboard():
    notifications = Notification.query.filter(
        Notification.target_role.in_(['all', 'student']),
        or_(
            Notification.branch_id == current_user.branch_id,
            Notification.branch_id.is_(None),
        ),
    ).order_by(Notification.created_at.desc()).limit(5).all()

    at_risk = get_low_attendance_risk(current_user)
    prediction = predict_student_performance(current_user)
    attendance_entries = Attendance.query.filter_by(student_id=current_user.id).all()
    total_sessions = len(attendance_entries)
    attended_sessions = sum(1 for entry in attendance_entries if entry.status)
    attendance_percentage = round((attended_sessions / total_sessions) * 100, 1) if total_sessions else 0.0

    return render_template(
        'student/dashboard.html',
        notifications=notifications,
        at_risk=at_risk,
        prediction=prediction,
        attendance_summary={
            'total_sessions': total_sessions,
            'attended_sessions': attended_sessions,
            'percentage': attendance_percentage,
        },
    )


@student_bp.route('/attendance')
def attendance():
    subjects = Subject.query.filter_by(branch_id=current_user.branch_id).all()
    attendance_data = {}
    for sub in subjects:
        atts = Attendance.query.filter_by(student_id=current_user.id, subject_id=sub.id).all()
        total = len(atts)
        present = sum(1 for attendance_record in atts if attendance_record.status)
        attendance_data[sub.name] = {
            'total': total,
            'present': present,
            'percentage': round((present / total) * 100, 2) if total > 0 else 0.0,
        }
    return render_template('student/attendance.html', attendance_data=attendance_data)


@student_bp.route('/calendar')
def calendar():
    calendar_data = build_branch_calendar(
        current_user.branch_id,
        semester=request.args.get('semester', type=int),
        month=request.args.get('month', type=int),
        year=request.args.get('year', type=int),
        user=current_user,
    )
    return render_template(
        'calendar/calendar.html',
        calendar_data=calendar_data,
        can_manage=False,
        edit_event=None,
        back_endpoint='student.dashboard',
        calendar_endpoint='student.calendar',
        page_title='Academic Calendar',
        page_heading='Track semester-specific exams, holidays, and academic events from one calendar.',
        page_description='View the schedule for your branch and selected semester in a clean monthly layout with date-wise details.',
    )


@student_bp.route('/api/calendar')
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


@student_bp.route('/results')
def results():
    from app.models import Marks

    marks = Marks.query.filter_by(student_id=current_user.id).all()
    released_marks = [mark for mark in marks if mark.exam.results_released]
    return render_template('student/results.html', marks=released_marks)


@student_bp.route('/timetable')
def timetable():
    from app.models import Timetable

    day_order = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6,
    }
    timetable_data = (
        Timetable.query.filter_by(
            branch_id=current_user.branch_id,
            division_id=current_user.division_id,
        )
        .all()
    )
    timetable_data.sort(key=lambda slot: (day_order.get(slot.day_of_week, 99), slot.start_time, slot.subject.name))
    days = {}
    for timeslot in timetable_data:
        days.setdefault(timeslot.day_of_week, []).append(timeslot)
    return render_template('student/timetable.html', timetable=days)


@student_bp.route('/assignments')
def assignments():
    assignment_cards = build_student_assignment_cards(current_user)
    summary = {
        'total': len(assignment_cards),
        'submitted_count': sum(1 for card in assignment_cards if card['is_submitted']),
        'pending_count': sum(1 for card in assignment_cards if card['status'] == 'Pending'),
        'late_count': sum(1 for card in assignment_cards if card['status'] == 'Late'),
    }
    return render_template('student/assignments.html', assignment_cards=assignment_cards, assignment_summary=summary)


@student_bp.route('/assignments/<int:assignment_id>/submit', methods=['GET', 'POST'])
def submit_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    if not can_student_access_assignment(current_user, assignment):
        flash("You do not have access to this assignment.", "danger")
        return redirect(url_for('student.assignments'))

    submission = get_submission_for_student(assignment.id, current_user.id)

    if request.method == 'POST':
        submission_text = (request.form.get('submission_text') or '').strip() or None
        submission_file = request.files.get('submission_file')
        existing_file_path = submission.file_path if submission else None

        if submission is None:
            submission = Submission(assignment_id=assignment.id, student_id=current_user.id)
            db.session.add(submission)

        try:
            if submission_file and submission_file.filename:
                file_path, original_name = save_submission_file(submission_file)
                submission.file_path = file_path
                submission.original_file_name = original_name
            elif not existing_file_path:
                submission.file_path = None
                submission.original_file_name = None
        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for('student.submit_assignment', assignment_id=assignment.id))

        if not submission_text and not submission.file_path:
            flash("Please add submission text or upload a file before submitting.", "danger")
            return redirect(url_for('student.submit_assignment', assignment_id=assignment.id))

        submission.submission_text = submission_text
        submission.submitted_at = datetime.utcnow()
        db.session.commit()
        flash("Assignment submitted successfully.", "success")
        return redirect(url_for('student.submit_assignment', assignment_id=assignment.id))

    return render_template(
        'student/assignment_submit.html',
        assignment=assignment,
        submission=submission,
        assignment_card=build_assignment_card(assignment, submission=submission),
    )


@student_bp.route('/leaves', methods=['GET', 'POST'])
def leave_requests():
    guardians = get_student_guardians(current_user)

    if request.method == 'POST':
        if not can_student_apply_leave(current_user):
            flash("A local guardian must be assigned before you can apply for leave.", "danger")
            return redirect(url_for('student.leave_requests'))

        reason = (request.form.get('reason') or '').strip()
        start_date_raw = request.form.get('start_date')
        end_date_raw = request.form.get('end_date')

        if not reason or not start_date_raw or not end_date_raw:
            flash("Reason, start date, and end date are required.", "danger")
            return redirect(url_for('student.leave_requests'))

        try:
            start_date = parse_leave_date(start_date_raw)
            end_date = parse_leave_date(end_date_raw)
        except ValueError:
            flash("Please enter valid leave dates.", "danger")
            return redirect(url_for('student.leave_requests'))

        if end_date < start_date:
            flash("End date cannot be earlier than the start date.", "danger")
            return redirect(url_for('student.leave_requests'))

        leave_request = LeaveRequest(
            student_id=current_user.id,
            reason=reason,
            start_date=start_date,
            end_date=end_date,
        )
        db.session.add(leave_request)
        db.session.commit()
        flash("Leave request submitted for local guardian review.", "success")
        return redirect(url_for('student.leave_requests'))

    leave_cards = build_student_leave_cards(current_user)
    leave_summary = {
        'total': len(leave_cards),
        'pending_count': sum(1 for card in leave_cards if card['request'].status == 'Pending'),
        'approved_count': sum(1 for card in leave_cards if card['request'].status == 'Approved'),
        'rejected_count': sum(1 for card in leave_cards if card['request'].status == 'Rejected'),
    }
    return render_template(
        'student/leaves.html',
        guardians=guardians,
        can_apply_leave=bool(guardians),
        leave_cards=leave_cards,
        leave_summary=leave_summary,
    )


@student_bp.route('/performance')
def performance_dashboard():
    performance_report = build_subject_performance(current_user)
    return render_template(
        'student/performance.html',
        performance_summary=performance_report['summary'],
        performance_insights=generate_performance_insights(performance_report['subjects']),
    )


@student_bp.route('/api/performance/subjects')
def performance_subject_marks_api():
    performance_report = build_subject_performance(current_user)
    return jsonify(
        {
            'subjects': performance_report['subjects'],
            'summary': performance_report['summary'],
            'insights': generate_performance_insights(performance_report['subjects']),
        }
    )


@student_bp.route('/api/performance/history')
def performance_history_api():
    return jsonify(build_performance_history(current_user))


@student_bp.route('/reports')
def reports_home():
    return render_template('student/reports_home.html', reports_overview=build_reports_overview(current_user))


@student_bp.route('/reports/monthly-attendance')
def monthly_attendance_report():
    selected_month = request.args.get('month', type=int)
    selected_year = request.args.get('year', type=int)
    report = build_monthly_attendance_report(current_user, month=selected_month, year=selected_year)
    return render_template(
        'student/report_attendance.html',
        report=report,
        month_options=get_month_options(),
    )


@student_bp.route('/reports/semester-results')
def semester_result_report():
    selected_semester = request.args.get('semester', type=int)
    report = build_semester_result_report(current_user, semester=selected_semester)
    return render_template('student/report_results.html', report=report)


@student_bp.route('/reports/remarks')
def remarks_report():
    selected_month = request.args.get('month', type=int)
    selected_year = request.args.get('year', type=int)
    selected_semester = request.args.get('semester', type=int)
    report = build_remarks_report(
        current_user,
        semester=selected_semester,
        month=selected_month,
        year=selected_year,
    )
    return render_template(
        'student/report_remarks.html',
        report=report,
        month_options=get_month_options(),
    )


@student_bp.route('/api/reports/monthly-attendance')
def monthly_attendance_report_api():
    selected_month = request.args.get('month', type=int)
    selected_year = request.args.get('year', type=int)
    return jsonify(build_monthly_attendance_report(current_user, month=selected_month, year=selected_year))


@student_bp.route('/api/reports/semester-results')
def semester_result_report_api():
    selected_semester = request.args.get('semester', type=int)
    return jsonify(build_semester_result_report(current_user, semester=selected_semester))


@student_bp.route('/api/reports/remarks')
def remarks_report_api():
    selected_month = request.args.get('month', type=int)
    selected_year = request.args.get('year', type=int)
    selected_semester = request.args.get('semester', type=int)
    return jsonify(
        build_remarks_report(
            current_user,
            semester=selected_semester,
            month=selected_month,
            year=selected_year,
        )
    )
