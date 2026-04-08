from app import create_app, db
from app.models import User, Branch, Division

app = create_app()

with app.app_context():
    db.create_all()

    # Create root admin if not exists
    admin_email = 'admin@example.com'
    if not User.query.filter_by(email=admin_email).first():
        admin = User(
            first_name='Super',
            last_name='Admin',
            email=admin_email,
            role='admin',
            verified=True
        )
        admin.set_password('admin123')
        db.session.add(admin)

    # Pre-seed some branches
    branches_to_create = ['Data Science', 'Mechanical Engineering', 'Computer Engineering']
    for b_name in branches_to_create:
        if not Branch.query.filter_by(name=b_name).first():
            b = Branch(name=b_name)
            db.session.add(b)

    db.session.commit()
    print("Database initialized successfully. Login as admin@example.com / admin123")
