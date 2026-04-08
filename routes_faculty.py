from flask import Blueprint, jsonify, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Assignment, LeaveRequest, Submission, User, Subject, Attendance, Exam, Marks, Division
from app.services.academic_calendar_service import build_branch_calendar, build_calendar_api_payload
from app.services.assignment_service import (
    build_assignment_submission_rows,
    build_faculty_assignment_cards,
    can_faculty_manage_assignment,
    can_faculty_manage_subject,
    get_faculty_subjects,
    parse_due_date,
)
from app.services.leave_service import (
    LEAVE_STATUSES,
    build_guardian_leave_cards,
    can_guardian_review_leave_request,
)
from app.utils import role_required, get_low_attendance_risk
from datetime import datetime

faculty_bp = Blueprint('faculty', __name__)

@faculty_bp.before_request
@login_required
@role_required('faculty')
def check_faculty():
    pass

@faculty_bp.route('/')
def dashboard():
    subjects = current_user.subjects_taught
    total_exams = sum(len(subject.exams) for subject in subjects)
    total_assignments = Assignment.query.filter_by(faculty_id=current_user.id).count()
    pending_leave_requests = sum(1 for student in current_user.local_guardian_students for leave_request in student.leave_requests if leave_request.status == 'Pending')
    return render_template(
        'faculty/dashboard.html',
        subjects=subjects,
        total_exams=total_exams,
        total_assignments=total_assignments,
        pending_leave_requests=pending_leave_requests,
    )


@faculty_bp.route('/calendar')
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
        back_endpoint='faculty.dashboard',
        calendar_endpoint='faculty.calendar',
        page_title='Academic Calendar',
        page_heading='Review branch schedules semester by semester from a clean calendar view.',
        page_description='View exams, holidays, and academic events for your branch and selected semester without editing access.',
    )


@faculty_bp.route('/api/calendar')
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


@faculty_bp.route('/assignments', methods=['GET', 'POST'])
def assignments():
    subjects = get_faculty_subjects(current_user)

    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        due_date_raw = request.form.get('due_date')
        subject_id = request.form.get('subject_id', type=int)
        if not subject_id:
            flash("Please select a subject for the assignment.", "danger")
            return redirect(url_for('faculty.assignments'))
        subject = Subject.query.get_or_404(subject_id)

        if not can_faculty_manage_subject(current_user, subject):
            flash("You can only create assignments for your assigned subjects.", "danger")
            return redirect(url_for('faculty.assignments'))

        if not title or not description or not due_date_raw:
            flash("Title, description, and due date are required.", "danger")
            return redirect(url_for('faculty.assignments'))

        try:
            due_date = parse_due_date(due_date_raw)
        except ValueError:
            flash("Please enter a valid due date.", "danger")
            return redirect(url_for('faculty.assignments'))

        assignment = Assignment(
            title=title,
            description=description,
            due_date=due_date,
            subject_id=subject.id,
            faculty_id=current_user.id,
        )
        db.session.add(assignment)
        db.session.commit()
        flash(f"Assignment '{title}' created successfully.", "success")
        return redirect(url_for('faculty.assignments'))

    assignment_cards = build_faculty_assignment_cards(current_user)
    assignment_summary = {
        'total': len(assignment_cards),
        'submitted_count': sum(card['submitted_count'] for card in assignment_cards),
        'late_count': sum(card['late_count'] for card in assignment_cards),
    }

    return render_template(
        'faculty/assignments.html',
        subjects=subjects,
        assignment_cards=assignment_cards,
        assignment_summary=assignment_summary,
    )


@faculty_bp.route('/assignments/<int:assignment_id>/submissions')
def assignment_submissions(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    if not can_faculty_manage_assignment(current_user, assignment):
        flash("You do not have permission to view submissions for this assignment.", "danger")
        return redirect(url_for('faculty.assignments'))

    submission_rows = build_assignment_submission_rows(assignment)
    summary = {
        'student_count': len(submission_rows),
        'submitted_count': sum(1 for row in submission_rows if row['submission']),
        'late_count': sum(1 for row in submission_rows if row['status'] == 'Late'),
        'graded_count': sum(1 for row in submission_rows if row['submission'] and row['submission'].grade is not None),
    }

    return render_template(
        'faculty/assignment_submissions.html',
        assignment=assignment,
        submission_rows=submission_rows,
        submission_summary=summary,
    )


@faculty_bp.route('/submissions/<int:submission_id>/grade', methods=['POST'])
def grade_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    if not can_faculty_manage_assignment(current_user, submission.assignment):
        flash("You do not have permission to grade this submission.", "danger")
        return redirect(url_for('faculty.assignments'))

    grade_raw = (request.form.get('grade') or '').strip()
    feedback = (request.form.get('feedback') or '').strip() or None

    try:
        grade = float(grade_raw) if grade_raw else None
    except ValueError:
        flash("Grade must be a valid number.", "danger")
        return redirect(url_for('faculty.assignment_submissions', assignment_id=submission.assignment_id))

    submission.grade = grade
    submission.feedback = feedback
    submission.graded_at = datetime.utcnow() if (grade is not None or feedback) else None
    db.session.commit()
    flash("Submission grade and feedback updated.", "success")
    return redirect(url_for('faculty.assignment_submissions', assignment_id=submission.assignment_id))


@faculty_bp.route('/leave-requests')
def leave_requests():
    leave_cards = build_guardian_leave_cards(current_user)
    leave_summary = {
        'total': len(leave_cards),
        'pending_count': sum(1 for card in leave_cards if card['request'].status == 'Pending'),
        'approved_count': sum(1 for card in leave_cards if card['request'].status == 'Approved'),
        'rejected_count': sum(1 for card in leave_cards if card['request'].status == 'Rejected'),
    }
    return render_template('faculty/leave_requests.html', leave_cards=leave_cards, leave_summary=leave_summary)


@faculty_bp.route('/leave-requests/<int:leave_request_id>/review', methods=['POST'])
def review_leave_request(leave_request_id):
    leave_request = LeaveRequest.query.get_or_404(leave_request_id)
    if not can_guardian_review_leave_request(current_user, leave_request):
        flash("You do not have permission to review this leave request.", "danger")
        return redirect(url_for('faculty.leave_requests'))

    status = (request.form.get('status') or '').strip().title()
    if status not in LEAVE_STATUSES or status == 'Pending':
        flash("Please choose a valid review action.", "danger")
        return redirect(url_for('faculty.leave_requests'))

    if leave_request.status != 'Pending':
        flash("This leave request has already been reviewed.", "warning")
        return redirect(url_for('faculty.leave_requests'))

    leave_request.status = status
    leave_request.reviewed_by_id = current_user.id
    leave_request.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash(f"Leave request {status.lower()} successfully.", "success")
    return redirect(url_for('faculty.leave_requests'))

@faculty_bp.route('/attendance/<int:subject_id>', methods=['GET', 'POST'])
def mark_attendance(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject not in current_user.subjects_taught:
        flash("You do not have permission to modify attendance for this subject.", "danger")
        return redirect(url_for('faculty.dashboard'))

    students = User.query.filter_by(role='student', branch_id=subject.branch_id, verified=True).all()

    if request.method == 'POST':
        date_str = request.form.get('date')
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        present_student_ids = request.form.getlist('student_ids') # returns list of strings 'id'

        for student in students:
            # check if attendance already exists
            att = Attendance.query.filter_by(student_id=student.id, subject_id=subject.id, date=date_obj).first()
            status = str(student.id) in present_student_ids
            if att:
                att.status = status
            else:
                new_att = Attendance(student_id=student.id, subject_id=subject.id, date=date_obj, status=status)
                db.session.add(new_att)
        db.session.commit()
        flash(f"Attendance marked for {date_str}", "success")
        return redirect(url_for('faculty.dashboard'))

    today = datetime.utcnow().strftime('%Y-%m-%d')
    return render_template('faculty/attendance.html', subject=subject, students=students, today=today)

@faculty_bp.route('/marks/<int:exam_id>', methods=['GET', 'POST'])
def enter_marks(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.subject not in current_user.subjects_taught:
        flash("You do not have permission to view these marks.", "danger")
        return redirect(url_for('faculty.dashboard'))

    students = User.query.filter_by(role='student', branch_id=exam.subject.branch_id, verified=True).all()

    if request.method == 'POST':
        for student in students:
            val = request.form.get(f'marks_{student.id}')
            if val is not None and val != '':
                val_float = float(val)
                # check if marks already exist
                mark = Marks.query.filter_by(student_id=student.id, exam_id=exam.id).first()
                if mark:
                    mark.marks_obtained = val_float
                else:
                    new_mark = Marks(student_id=student.id, exam_id=exam.id, marks_obtained=val_float)
                    db.session.add(new_mark)
        db.session.commit()
        flash("Marks updated.", "success")
        return redirect(url_for('faculty.dashboard'))

    # pre-fetch existing marks
    existing_marks = {m.student_id: m.marks_obtained for m in exam.marks}
    return render_template('faculty/marks.html', exam=exam, students=students, existing_marks=existing_marks)
