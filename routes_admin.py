from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import User, Branch, Division
from app.utils import role_required

admin_bp = Blueprint('admin', __name__)

@admin_bp.before_request
@login_required
@role_required('admin')
def check_admin():
    pass

@admin_bp.route('/')
def dashboard():
    pending_hods = User.query.filter_by(role='hod', verified=False).all()
    branches = Branch.query.count()
    students = User.query.filter_by(role='student').count()
    faculty = User.query.filter_by(role='faculty').count()
    
    return render_template('admin/dashboard.html', 
                           pending_hods=pending_hods, 
                           stats={'branches': branches, 'students': students, 'faculty': faculty})

@admin_bp.route('/verify/<int:user_id>', methods=['POST'])
def verify_hod(user_id):
    hod = User.query.get_or_404(user_id)
    if hod.role == 'hod':
        hod.verified = True
        db.session.commit()
        flash(f"HOD {hod.first_name} {hod.last_name} has been verified.", "success")
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/branches', methods=['GET', 'POST'])
def manage_branches():
    if request.method == 'POST':
        name = request.form.get('name')
        if Branch.query.filter_by(name=name).first():
            flash("Branch already exists.", "danger")
        else:
            new_branch = Branch(name=name)
            db.session.add(new_branch)
            db.session.commit()
            flash(f"Branch {name} created.", "success")
        return redirect(url_for('admin.manage_branches'))

    branches = Branch.query.all()
    return render_template('admin/branches.html', branches=branches)
