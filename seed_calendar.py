"""Run once to seed database, then remove or disable."""

from datetime import datetime

from app import create_app, db
from app.models import Branch, CalendarEvent


BRANCH_NAME = "Data Science"
SEMESTER = 4
CALENDAR_ENTRIES = [
    {"date": "2026-02-04", "title": "Teaching Start", "type": "event"},
    {"date": "2026-03-02", "title": "Detention List 1", "type": "event"},
    {"date": "2026-03-03", "title": "Dhulivandan", "type": "holiday"},
    {"date": "2026-03-06", "title": "Converges 2K26 / Annual Gathering", "type": "event"},
    {"date": "2026-03-07", "title": "Converges 2K26", "type": "event"},
    {"date": "2026-03-14", "title": "Staff Feedback 1 (ERP)", "type": "event"},
    {"date": "2026-03-14", "title": "Internship Project Title Finalization", "type": "event"},
    {"date": "2026-03-19", "title": "Shivaji Maharaj Jayanti", "type": "holiday"},
    {"date": "2026-03-19", "title": "Gudi Padwa", "type": "holiday"},
    {"date": "2026-03-21", "title": "Ramjan Eid", "type": "holiday"},
    {"date": "2026-03-26", "title": "Shriram Navami", "type": "holiday"},
    {"date": "2026-03-27", "title": "Internship Monitoring 1", "type": "event"},
    {"date": "2026-03-28", "title": "Project Monitoring 1", "type": "event"},
    {"date": "2026-04-02", "title": "Detention List 2", "type": "event"},
    {"date": "2026-04-03", "title": "Good Friday", "type": "holiday"},
    {"date": "2026-04-06", "title": "TT-1 (Term Test 1)", "type": "exam"},
    {"date": "2026-04-07", "title": "TT-1 (Term Test 1)", "type": "exam"},
    {"date": "2026-04-08", "title": "TT-1 (Term Test 1)", "type": "exam"},
    {"date": "2026-04-14", "title": "Dr. Babasaheb Ambedkar Jayanti", "type": "holiday"},
    {"date": "2026-04-15", "title": "Presentations", "type": "event"},
    {"date": "2026-04-16", "title": "Presentations", "type": "event"},
    {"date": "2026-04-17", "title": "Presentations", "type": "event"},
    {"date": "2026-04-25", "title": "Staff Feedback 1 (ERP)", "type": "event"},
    {"date": "2026-04-27", "title": "Internship Monitoring 2", "type": "event"},
    {"date": "2026-04-28", "title": "Mock Interview", "type": "event"},
    {"date": "2026-04-29", "title": "Mock Interview", "type": "event"},
    {"date": "2026-04-30", "title": "Mock Interview", "type": "event"},
    {"date": "2026-05-04", "title": "Detention List 3", "type": "event"},
    {"date": "2026-05-05", "title": "TT-2 (Term Test 2)", "type": "exam"},
    {"date": "2026-05-06", "title": "TT-2 (Term Test 2)", "type": "exam"},
    {"date": "2026-05-07", "title": "TT-2 (Term Test 2)", "type": "exam"},
    {"date": "2026-05-08", "title": "Internship Monitoring 3", "type": "event"},
    {"date": "2026-05-09", "title": "Project Monitoring 3", "type": "event"},
    {"date": "2026-05-16", "title": "Teaching End", "type": "event"},
    {"date": "2026-05-18", "title": "Start of Theory Exam", "type": "exam"},
    {"date": "2026-05-27", "title": "Bakrid", "type": "holiday"},
    {"date": "2026-06-06", "title": "End of Theory Exam", "type": "exam"},
    {"date": "2026-06-08", "title": "Start of Practical Exam", "type": "exam"},
    {"date": "2026-06-18", "title": "End of Practical Exam", "type": "exam"},
]


def seed_calendar():
    app = create_app()
    with app.app_context():
        branch = Branch.query.filter_by(name=BRANCH_NAME).first()
        if branch is None:
            raise RuntimeError(f"Branch '{BRANCH_NAME}' was not found. Create it before running this script.")

        existing_keys = {
            (event.date.isoformat(), event.title, event.type)
            for event in CalendarEvent.query.filter_by(branch_id=branch.id, semester=SEMESTER).all()
        }

        inserted_count = 0
        skipped_count = 0

        for entry in CALENDAR_ENTRIES:
            event_key = (entry["date"], entry["title"], entry["type"])
            if event_key in existing_keys:
                skipped_count += 1
                continue

            calendar_event = CalendarEvent(
                title=entry["title"],
                date=datetime.strptime(entry["date"], "%Y-%m-%d").date(),
                type=entry["type"],
                branch_id=branch.id,
                semester=SEMESTER,
                description=None,
            )
            db.session.add(calendar_event)
            existing_keys.add(event_key)
            inserted_count += 1

        db.session.commit()
        print(
            f"Seed complete for {BRANCH_NAME} semester {SEMESTER}. "
            f"Inserted: {inserted_count}, skipped existing: {skipped_count}"
        )


if __name__ == "__main__":
    seed_calendar()
