"""Run once, then disable or remove."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
from itertools import permutations
import random

from app import create_app, db
from app.config import Config
from app.models import (
    Assignment,
    Attendance,
    Branch,
    CalendarEvent,
    Division,
    Exam,
    LeaveRequest,
    Marks,
    Notification,
    Subject,
    Submission,
    Timetable,
    User,
)


BRANCH_NAME = "Data Science"
SEMESTER = 4
DIVISION_NAMES = ("DS-A", "DS-B")
DEFAULT_PASSWORD = "Academia@123"
PRN_PREFIX = "241106"
STUDENTS_PER_DIVISION = 60
ATTENDANCE_LECTURES_PER_SUBJECT = 24
CORE_SUBJECT_CODES = ("DS", "ML-I", "SDS", "EFM", "PBC", "WEL", "OE")
TIMETABLE_ONLY_SUBJECT_CODES = ("PSS", "MPS", "Sem Project", "Library Hr.")
SEED_RANDOM = random.Random(241106)
DAY_SEQUENCE = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
DAY_TO_WEEKDAY = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}
TIME_SLOTS = {
    1: ("09:20", "10:10"),
    2: ("10:10", "11:00"),
    3: ("11:50", "12:40"),
    4: ("12:40", "13:30"),
    5: ("13:45", "14:35"),
    6: ("14:35", "15:25"),
    7: ("15:25", "17:20"),
}
SUBJECT_FACULTY_MAP = {
    "DS": ("Dr. P. S. Sanjekar",),
    "ML-I": ("Dr. U. M. Patil",),
    "SDS": ("Prof. A. B. Patil", "Dr. M. S. Patil"),
    "OE": ("Dr. K. D. Chaudhari",),
    "EFM": ("Prof. K. D. Deore",),
    "PBC": ("Prof. Surekha Patil",),
    "WEL": ("Prof. S. K. Bhandare",),
    "PSS": ("Dr. U. M. Patil", "Prof. S. K. Bhandare"),
    "MPS": ("Prof. S. K. Bhandare",),
    "Sem Project": ("Dr. K. D. Chaudhari",),
    "Library Hr.": ("Dr. K. D. Chaudhari",),
}
FACULTY_DIRECTORY = (
    {
        "full_name": "Dr. P. S. Sanjekar",
        "email": "ps.sanjekar@academiapro.local",
        "subject_codes": ("DS",),
    },
    {
        "full_name": "Dr. U. M. Patil",
        "email": "um.patil@academiapro.local",
        "subject_codes": ("ML-I", "PSS"),
    },
    {
        "full_name": "Prof. A. B. Patil",
        "email": "ab.patil@academiapro.local",
        "subject_codes": ("SDS",),
    },
    {
        "full_name": "Dr. M. S. Patil",
        "email": "ms.patil@academiapro.local",
        "subject_codes": ("SDS",),
    },
    {
        "full_name": "Dr. K. D. Chaudhari",
        "email": "kd.chaudhari@academiapro.local",
        "subject_codes": ("OE", "Sem Project", "Library Hr."),
    },
    {
        "full_name": "Prof. K. D. Deore",
        "email": "kd.deore@academiapro.local",
        "subject_codes": ("EFM",),
    },
    {
        "full_name": "Prof. Surekha Patil",
        "email": "surekha.patil@academiapro.local",
        "subject_codes": ("PBC",),
    },
    {
        "full_name": "Prof. S. K. Bhandare",
        "email": "sk.bhandare@academiapro.local",
        "subject_codes": ("WEL", "PSS", "MPS"),
    },
)
NOTIFICATION_MESSAGES = (
    ("all", "Semester 4 teaching plan for Data Science is now active for both DS-A and DS-B."),
    ("student", "TT-1 preparation support sessions will be announced department-wise this week."),
    ("faculty", "Upload attendance regularly to keep student analytics and reports accurate."),
    ("all", "Project monitoring checkpoints have been aligned with the semester activity plan."),
    ("student", "Assignment and leave request dashboards are now ready for regular use."),
    ("faculty", "Please review assignment submissions and publish feedback before TT-2."),
    ("all", "Industry interaction and seminar activities will continue through the semester."),
    ("student", "Keep attendance above 75% to avoid detention and remarks risk."),
)
LEAVE_REASONS = (
    "Medical consultation and recovery rest.",
    "Family function outside the city.",
    "Travel required for a personal emergency.",
    "Project-related visit with prior faculty approval.",
)


def parse_clock(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def split_full_name(full_name: str) -> tuple[str, str]:
    if full_name.startswith(("Dr. ", "Prof. ")):
        prefix, remainder = full_name.split(" ", 1)
        return prefix, remainder
    first_name, _, last_name = full_name.partition(" ")
    return first_name, last_name


def upsert_user(
    *,
    email: str,
    role: str,
    first_name: str,
    last_name: str,
    branch: Branch | None = None,
    division: Division | None = None,
    verified: bool = True,
    prn: str | None = None,
    roll_no: int | None = None,
    password: str = DEFAULT_PASSWORD,
) -> User:
    with db.session.no_autoflush:
        user = User.query.filter_by(email=email).first()
        if user is None and prn:
            user = User.query.filter_by(prn=prn).first()

    if user is None:
        user = User(email=email, role=role)
        user.set_password(password)
        db.session.add(user)

    user.first_name = first_name
    user.last_name = last_name
    user.role = role
    user.verified = verified

    if branch is not None:
        user.branch_ref = branch
    if division is not None:
        user.division_ref = division

    if prn is not None:
        user.prn = prn
    if roll_no is not None:
        user.roll_no = roll_no

    email_owner = None
    with db.session.no_autoflush:
        email_owner = User.query.filter_by(email=email).first()

    if email_owner is None or email_owner.id == user.id:
        user.email = email

    return user


def get_or_create_branch() -> Branch:
    branch = Branch.query.filter_by(name=BRANCH_NAME).first()
    if branch is None:
        branch = Branch(name=BRANCH_NAME)
        db.session.add(branch)
        db.session.flush()
    return branch


def get_or_create_divisions(branch: Branch) -> dict[str, Division]:
    divisions = {}
    for division_name in DIVISION_NAMES:
        division = Division.query.filter_by(branch_id=branch.id, name=division_name).first()
        if division is None:
            division = Division(name=division_name, branch=branch)
            db.session.add(division)
        divisions[division_name] = division
    db.session.flush()
    return divisions


def get_or_create_admin() -> User:
    admin = User.query.filter_by(email="admin@example.com").first()
    if admin is None:
        admin = User(
            first_name="Super",
            last_name="Admin",
            email="admin@example.com",
            role="admin",
            verified=True,
        )
        admin.set_password("admin123")
        db.session.add(admin)
    return admin


def get_or_create_hod(branch: Branch) -> User:
    return upsert_user(
        email="hod.datascience@academiapro.local",
        role="hod",
        first_name="Dr.",
        last_name="Meera Kulkarni",
        branch=branch,
        verified=True,
    )


def seed_faculty(branch: Branch) -> dict[str, User]:
    faculty_by_name = {}
    for record in FACULTY_DIRECTORY:
        first_name, last_name = split_full_name(record["full_name"])
        faculty = upsert_user(
            email=record["email"],
            role="faculty",
            first_name=first_name,
            last_name=last_name,
            branch=branch,
            verified=True,
        )
        faculty_by_name[record["full_name"]] = faculty
    db.session.flush()
    return faculty_by_name


def generate_student_name(index: int) -> tuple[str, str]:
    first_names = (
        "Aarav",
        "Advait",
        "Aditya",
        "Akshay",
        "Aniket",
        "Atharva",
        "Omkar",
        "Parth",
        "Pranav",
        "Rohan",
        "Sarthak",
        "Shreyas",
        "Siddharth",
        "Tanmay",
        "Vedant",
        "Yash",
        "Aditi",
        "Ananya",
        "Isha",
        "Kavya",
    )
    surnames = ("Patil", "Kulkarni", "Shinde", "Jadhav", "Joshi", "Deshmukh")
    return first_names[index % len(first_names)], surnames[index // len(first_names)]


def seed_students(branch: Branch, divisions: dict[str, Division]) -> dict[str, list[User]]:
    seeded_students = {division_name: [] for division_name in DIVISION_NAMES}
    global_index = 1

    for division_name in DIVISION_NAMES:
        division = divisions[division_name]
        for roll_no in range(1, STUDENTS_PER_DIVISION + 1):
            first_name, last_name = generate_student_name(global_index - 1)
            prn = f"{PRN_PREFIX}{global_index:03d}"
            email = f"{prn}@student.academiapro.local"
            student = upsert_user(
                email=email,
                role="student",
                first_name=first_name,
                last_name=last_name,
                branch=branch,
                division=division,
                verified=True,
                prn=prn,
                roll_no=roll_no,
            )
            seeded_students[division_name].append(student)
            global_index += 1

    db.session.flush()
    return seeded_students


def seed_subjects(branch: Branch) -> dict[str, Subject]:
    subject_codes = CORE_SUBJECT_CODES + TIMETABLE_ONLY_SUBJECT_CODES
    subject_by_code = {}
    for subject_code in subject_codes:
        subject = Subject.query.filter_by(branch_id=branch.id, name=subject_code, semester=SEMESTER).first()
        if subject is None:
            subject = Subject(name=subject_code, branch=branch, semester=SEMESTER)
            db.session.add(subject)
        subject_by_code[subject_code] = subject
    db.session.flush()
    return subject_by_code


def assign_faculty_to_subjects(faculty_by_name: dict[str, User], subject_by_code: dict[str, Subject]) -> None:
    for subject_code, faculty_names in SUBJECT_FACULTY_MAP.items():
        subject = subject_by_code[subject_code]
        for faculty_name in faculty_names:
            faculty = faculty_by_name[faculty_name]
            if subject not in faculty.subjects_taught:
                faculty.subjects_taught.append(subject)


def enroll_students(students_by_division: dict[str, list[User]], subject_by_code: dict[str, Subject]) -> list[User]:
    enrolled_subjects = list(subject_by_code.values())
    all_students = []
    for division_students in students_by_division.values():
        for student in division_students:
            all_students.append(student)
            for subject in enrolled_subjects:
                if subject not in student.subjects_enrolled:
                    student.subjects_enrolled.append(subject)
    return all_students


def ds_a_schedule():
    return {
        "Monday": [
            {
                "slot": 1,
                "entries": [
                    {"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "practical", "group": "S2"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S3"},
                ],
            },
            {
                "slot": 2,
                "entries": [
                    {"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "practical", "group": "S1"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S2"},
                    {"subject": "PSS", "faculty": "Dr. U. M. Patil", "kind": "theory"},
                ],
            },
            {"slot": 3, "entries": [{"subject": "SDS", "faculty": "Prof. A. B. Patil", "kind": "theory"}]},
            {"slot": 4, "entries": [{"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "theory"}]},
            {"slot": 5, "entries": [{"subject": "EFM", "faculty": "Prof. K. D. Deore", "kind": "theory"}]},
            {"slot": 6, "entries": [{"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "theory"}]},
        ],
        "Tuesday": [
            {
                "slot": 1,
                "entries": [
                    {"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "practical", "group": "S1"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S2"},
                    {"subject": "PSS", "faculty": "Dr. U. M. Patil", "kind": "theory"},
                ],
            },
            {
                "slot": 2,
                "entries": [
                    {"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "practical", "group": "S1"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S2"},
                    {"subject": "PSS", "faculty": "Dr. U. M. Patil", "kind": "theory"},
                ],
            },
            {"slot": 3, "entries": [{"subject": "PBC", "faculty": "Prof. Surekha Patil", "kind": "theory"}]},
            {"slot": 4, "entries": [{"subject": "EFM", "faculty": "Prof. K. D. Deore", "kind": "theory"}]},
            {"slot": 5, "entries": [{"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "theory"}]},
            {"slot": 6, "entries": [{"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "theory"}]},
        ],
        "Wednesday": [
            {
                "slot": 1,
                "entries": [
                    {"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "practical", "group": "S1"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S2"},
                    {"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "practical", "group": "S3"},
                ],
            },
            {
                "slot": 2,
                "entries": [
                    {"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "practical", "group": "S1"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S2"},
                    {"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "practical", "group": "S3"},
                ],
            },
            {"slot": 3, "entries": [{"subject": "Sem Project", "faculty": "Dr. K. D. Chaudhari", "kind": "theory"}]},
            {"slot": 4, "entries": [{"subject": "SDS", "faculty": "Prof. A. B. Patil", "kind": "theory"}]},
            {"slot": 5, "entries": [{"subject": "OE", "faculty": "Dr. K. D. Chaudhari", "kind": "theory"}]},
            {"slot": 6, "entries": [{"subject": "OE", "faculty": "Dr. K. D. Chaudhari", "kind": "theory"}]},
        ],
        "Thursday": [
            {
                "slot": 1,
                "entries": [
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S1"},
                    {"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "practical", "group": "S2"},
                    {"subject": "SDS", "faculty": "Dr. M. S. Patil", "kind": "practical", "group": "S3"},
                ],
            },
            {
                "slot": 2,
                "entries": [
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S1"},
                    {"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "practical", "group": "S2"},
                    {"subject": "SDS", "faculty": "Dr. M. S. Patil", "kind": "practical", "group": "S3"},
                ],
            },
            {"slot": 3, "entries": [{"subject": "Library Hr.", "faculty": "Dr. K. D. Chaudhari", "kind": "theory"}]},
            {"slot": 4, "entries": [{"subject": "PBC", "faculty": "Prof. Surekha Patil", "kind": "theory"}]},
            {"slot": 5, "entries": [{"subject": "OE", "faculty": "Dr. K. D. Chaudhari", "kind": "theory"}]},
            {"slot": 6, "entries": [{"subject": "OE", "faculty": "Dr. K. D. Chaudhari", "kind": "theory"}]},
        ],
        "Friday": [
            {
                "slot": 1,
                "entries": [
                    {"subject": "SDS", "faculty": "Dr. M. S. Patil", "kind": "practical", "group": "S1"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S3"},
                    {"subject": "MPS", "faculty": "Prof. S. K. Bhandare", "kind": "theory"},
                ],
            },
            {
                "slot": 2,
                "entries": [
                    {"subject": "SDS", "faculty": "Dr. M. S. Patil", "kind": "practical", "group": "S1"},
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S3"},
                    {"subject": "MPS", "faculty": "Prof. S. K. Bhandare", "kind": "theory"},
                ],
            },
            {"slot": 3, "entries": [{"subject": "SDS", "faculty": "Prof. A. B. Patil", "kind": "theory"}]},
            {"slot": 4, "entries": [{"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "theory"}]},
            {"slot": 5, "entries": [{"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "theory"}]},
            {"slot": 6, "entries": [{"subject": "EFM", "faculty": "Prof. K. D. Deore", "kind": "theory"}]},
        ],
        "Saturday": [
            {
                "slot": 1,
                "entries": [
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S1"},
                    {"subject": "SDS", "faculty": "Dr. M. S. Patil", "kind": "practical", "group": "S2"},
                    {"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "practical", "group": "S3"},
                ],
            },
            {
                "slot": 2,
                "entries": [
                    {"subject": "WEL", "faculty": "Prof. S. K. Bhandare", "kind": "practical", "group": "S1"},
                    {"subject": "SDS", "faculty": "Dr. M. S. Patil", "kind": "practical", "group": "S2"},
                    {"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "practical", "group": "S3"},
                ],
            },
            {"slot": 3, "entries": [{"subject": "SDS", "faculty": "Prof. A. B. Patil", "kind": "theory"}]},
            {"slot": 4, "entries": [{"subject": "DS", "faculty": "Dr. P. S. Sanjekar", "kind": "theory"}]},
            {"slot": 5, "entries": [{"subject": "ML-I", "faculty": "Dr. U. M. Patil", "kind": "theory"}]},
            {"slot": 6, "entries": [{"subject": "Sem Project", "faculty": "Dr. K. D. Chaudhari", "kind": "theory"}]},
        ],
    }


def block_faculty_set(block) -> set[str]:
    return {entry["faculty"] for entry in block["entries"]}


def block_subject_signature(block) -> tuple[str, ...]:
    return tuple(sorted(entry["subject"] for entry in block["entries"]))


def is_practical_block(block) -> bool:
    return any(entry["kind"] == "practical" for entry in block["entries"])


def clone_block(block, slot):
    return {
        "slot": slot,
        "entries": [dict(entry) for entry in block["entries"]],
        "source_slot": block["slot"],
    }


def score_permutation(day_blocks, slot_assignments):
    score = 0
    preferred_targets = {1: 5, 2: 6, 3: 1, 4: 2, 5: 3, 6: 4}
    slot_to_ds_a_block = {block["slot"]: block for block in day_blocks}

    for source_block, target_slot in slot_assignments:
        faculty_conflict = block_faculty_set(source_block) & block_faculty_set(slot_to_ds_a_block[target_slot])
        if faculty_conflict:
            return None

        score += abs(target_slot - preferred_targets[source_block["slot"]]) * 4
        if target_slot == source_block["slot"]:
            score += 90

        if is_practical_block(source_block) and source_block["slot"] in (1, 2):
            if target_slot in (1, 2):
                score += 70
            elif target_slot in (3, 4):
                score += 25
        elif not is_practical_block(source_block) and source_block["slot"] in (5, 6):
            if target_slot in (5, 6):
                score += 14

    ordered_blocks = [
        next(block for block, mapped_slot in slot_assignments if mapped_slot == target_slot)
        for target_slot in range(1, 7)
    ]
    for previous_block, current_block in zip(ordered_blocks, ordered_blocks[1:]):
        repeated_subjects = set(block_subject_signature(previous_block)) & set(block_subject_signature(current_block))
        if repeated_subjects:
            score += 18

    return score


def generate_division_b_schedule(schedule_a):
    generated_schedule = {}
    for day in DAY_SEQUENCE:
        day_blocks = schedule_a[day]
        best_layout = None
        best_score = None

        for target_slots in permutations(range(1, 7)):
            slot_assignments = [(day_blocks[index], target_slots[index]) for index in range(len(day_blocks))]
            score = score_permutation(day_blocks, slot_assignments)
            if score is None:
                continue
            if best_score is None or score < best_score:
                best_score = score
                best_layout = [clone_block(block, target_slot) for block, target_slot in slot_assignments]

        if best_layout is None:
            raise RuntimeError(f"Unable to generate a conflict-free DS-B timetable for {day}.")

        best_layout.sort(key=lambda block: block["slot"])
        generated_schedule[day] = best_layout

    validate_division_b_schedule(schedule_a, generated_schedule)
    return generated_schedule


def validate_division_b_schedule(schedule_a, schedule_b):
    for day in DAY_SEQUENCE:
        counts_a = Counter(entry["subject"] for block in schedule_a[day] for entry in block["entries"])
        counts_b = Counter(entry["subject"] for block in schedule_b[day] for entry in block["entries"])
        if counts_a != counts_b:
            raise RuntimeError(f"DS-B subject distribution mismatch on {day}.")

        blocks_a = {block["slot"]: block for block in schedule_a[day]}
        blocks_b = {block["slot"]: block for block in schedule_b[day]}
        for slot in range(1, 7):
            faculty_overlap = block_faculty_set(blocks_a[slot]) & block_faculty_set(blocks_b[slot])
            if faculty_overlap:
                raise RuntimeError(f"Faculty conflict detected on {day} slot {slot}: {sorted(faculty_overlap)}")


def existing_timetable_keys(division_ids):
    rows = Timetable.query.filter(Timetable.division_id.in_(division_ids)).all()
    return {
        (row.division_id, row.day_of_week, row.start_time, row.end_time, row.subject_id, row.faculty_id)
        for row in rows
    }


def schedule_to_timetable_rows(schedule, division, branch, subject_by_code, faculty_by_name):
    rows = []
    for day, blocks in schedule.items():
        for block in blocks:
            start_value, end_value = TIME_SLOTS[block["slot"]]
            start_time = parse_clock(start_value)
            end_time = parse_clock(end_value)
            for entry in block["entries"]:
                rows.append(
                    Timetable(
                        branch_id=branch.id,
                        division_id=division.id,
                        subject_id=subject_by_code[entry["subject"]].id,
                        faculty_id=faculty_by_name[entry["faculty"]].id,
                        day_of_week=day,
                        start_time=start_time,
                        end_time=end_time,
                    )
                )
    return rows


def seed_timetables(branch, divisions, subject_by_code, faculty_by_name):
    schedule_a = ds_a_schedule()
    schedule_b = generate_division_b_schedule(schedule_a)
    existing_keys = existing_timetable_keys([division.id for division in divisions.values()])
    new_rows = []

    for division_name, schedule in (("DS-A", schedule_a), ("DS-B", schedule_b)):
        rows = schedule_to_timetable_rows(schedule, divisions[division_name], branch, subject_by_code, faculty_by_name)
        for row in rows:
            row_key = (row.division_id, row.day_of_week, row.start_time, row.end_time, row.subject_id, row.faculty_id)
            if row_key not in existing_keys:
                existing_keys.add(row_key)
                new_rows.append(row)

    if new_rows:
        db.session.bulk_save_objects(new_rows)

    return schedule_a, schedule_b


def collect_lecture_dates(day_names, total_count, start_date=date(2026, 2, 9)):
    lecture_dates = []
    current = start_date
    valid_weekdays = {DAY_TO_WEEKDAY[day_name] for day_name in day_names}
    while len(lecture_dates) < total_count:
        if current.weekday() in valid_weekdays:
            lecture_dates.append(current)
        current += timedelta(days=1)
    return lecture_dates


def subject_day_map(schedule):
    mapping = {}
    for day, blocks in schedule.items():
        for block in blocks:
            for entry in block["entries"]:
                mapping.setdefault(entry["subject"], set()).add(day)
    return mapping


def existing_attendance_keys(student_ids, subject_ids):
    rows = Attendance.query.filter(Attendance.student_id.in_(student_ids), Attendance.subject_id.in_(subject_ids)).all()
    return {(row.student_id, row.subject_id, row.date) for row in rows}


def seed_attendance(students, subject_by_code, schedule_a, schedule_b):
    lecture_day_map = subject_day_map(schedule_a)
    lecture_day_map_b = subject_day_map(schedule_b)
    for subject_code, day_names in lecture_day_map_b.items():
        lecture_day_map.setdefault(subject_code, set()).update(day_names)

    student_ids = [student.id for student in students]
    subject_ids = [subject.id for subject in subject_by_code.values()]
    existing_keys = existing_attendance_keys(student_ids, subject_ids)
    attendance_rows = []
    ordered_subject_codes = list(subject_by_code)

    for student_index, student in enumerate(students):
        for subject_index, subject_code in enumerate(ordered_subject_codes):
            subject = subject_by_code[subject_code]
            lecture_dates = collect_lecture_dates(
                sorted(lecture_day_map.get(subject_code, {"Monday", "Wednesday"})),
                ATTENDANCE_LECTURES_PER_SUBJECT,
            )
            target_percentage = 60 + ((student_index * 7 + subject_index * 5) % 36)
            present_count = round((target_percentage / 100) * len(lecture_dates))
            present_indices = set(SEED_RANDOM.sample(range(len(lecture_dates)), present_count))

            for date_index, lecture_date in enumerate(lecture_dates):
                row_key = (student.id, subject.id, lecture_date)
                if row_key in existing_keys:
                    continue
                existing_keys.add(row_key)
                attendance_rows.append(
                    Attendance(
                        student_id=student.id,
                        subject_id=subject.id,
                        date=lecture_date,
                        status=date_index in present_indices,
                    )
                )

    if attendance_rows:
        db.session.bulk_save_objects(attendance_rows)


def build_exam_dates():
    return {
        "TT-1": date(2026, 4, 6),
        "TT-2": date(2026, 5, 5),
        "Final": date(2026, 5, 18),
    }


def primary_faculty_for_subject(subject_code, faculty_by_name):
    return faculty_by_name[SUBJECT_FACULTY_MAP[subject_code][0]]


def seed_exams_and_marks(students, subject_by_code, faculty_by_name):
    exam_dates = build_exam_dates()
    subject_offsets = {code: index for index, code in enumerate(CORE_SUBJECT_CODES)}
    exams = {}

    for subject_code in CORE_SUBJECT_CODES:
        subject = subject_by_code[subject_code]
        for exam_name, base_date in exam_dates.items():
            exam = Exam.query.filter_by(subject_id=subject.id, name=exam_name).first()
            if exam is None:
                exam = Exam(
                    name=exam_name,
                    subject_id=subject.id,
                    date=base_date + timedelta(days=subject_offsets[subject_code]),
                    max_marks=100.0,
                    results_released=True,
                )
                db.session.add(exam)
            else:
                exam.results_released = True
                exam.max_marks = 100.0
            exams[(subject_code, exam_name)] = exam

    db.session.flush()

    existing_mark_keys = {(row.student_id, row.exam_id) for row in Marks.query.all()}
    mark_rows = []
    subject_modifiers = {
        "DS": 2,
        "ML-I": 1,
        "SDS": 0,
        "EFM": -3,
        "PBC": -1,
        "WEL": 4,
        "OE": 3,
    }
    exam_modifiers = {"TT-1": -4, "TT-2": 0, "Final": 3}

    for student_index, student in enumerate(students):
        base_score = 52 + (student_index % 18) * 2
        for subject_code in CORE_SUBJECT_CODES:
            for exam_name in exam_dates:
                exam = exams[(subject_code, exam_name)]
                mark_key = (student.id, exam.id)
                if mark_key in existing_mark_keys:
                    continue
                raw_score = base_score + subject_modifiers[subject_code] + exam_modifiers[exam_name] + SEED_RANDOM.randint(-8, 8)
                marks_obtained = max(40, min(95, raw_score))
                mark_rows.append(
                    Marks(
                        student_id=student.id,
                        exam_id=exam.id,
                        marks_obtained=float(marks_obtained),
                    )
                )
                existing_mark_keys.add(mark_key)

    if mark_rows:
        db.session.bulk_save_objects(mark_rows)


def build_assignment_payloads(now):
    payloads = []
    due_offsets = (-10, 4, 12)
    for subject_code in CORE_SUBJECT_CODES:
        for index, offset in enumerate(due_offsets, start=1):
            payloads.append(
                {
                    "subject_code": subject_code,
                    "title": f"{subject_code} Assignment {index}",
                    "description": (
                        f"Complete the {subject_code} assignment {index} with clear working, short notes, "
                        "and practical observations where relevant."
                    ),
                    "due_date": now + timedelta(days=offset, hours=index),
                }
            )
    return payloads


def seed_assignments_and_submissions(students, subject_by_code, faculty_by_name):
    now = datetime.utcnow()
    assignment_payloads = build_assignment_payloads(now)
    existing_assignments = {(row.subject_id, row.title): row for row in Assignment.query.all()}
    assignments = []

    for payload in assignment_payloads:
        subject = subject_by_code[payload["subject_code"]]
        faculty = primary_faculty_for_subject(payload["subject_code"], faculty_by_name)
        assignment = existing_assignments.get((subject.id, payload["title"]))
        if assignment is None:
            assignment = Assignment(
                title=payload["title"],
                description=payload["description"],
                due_date=payload["due_date"],
                subject_id=subject.id,
                faculty_id=faculty.id,
            )
            db.session.add(assignment)
        else:
            assignment.description = payload["description"]
            assignment.due_date = payload["due_date"]
            assignment.faculty_id = faculty.id
        assignments.append(assignment)

    db.session.flush()

    existing_submission_keys = {(row.assignment_id, row.student_id) for row in Submission.query.all()}
    submission_rows = []
    for assignment_index, assignment in enumerate(assignments):
        for student_index, student in enumerate(students):
            should_submit = ((student_index + assignment_index) % 10) < 7
            if not should_submit:
                continue

            submission_key = (assignment.id, student.id)
            if submission_key in existing_submission_keys:
                continue

            submitted_at = assignment.due_date - timedelta(days=((student_index + assignment_index) % 3))
            if (student_index + assignment_index) % 6 == 0:
                submitted_at = assignment.due_date + timedelta(hours=6)

            grade = None
            feedback = None
            graded_at = None
            if (student_index + assignment_index) % 4 != 0:
                grade = float(max(45, min(95, 58 + ((student_index * 3 + assignment_index * 5) % 38))))
                feedback = "Good structure and effort. Revise key concepts for even stronger answers."
                graded_at = submitted_at + timedelta(days=2)

            submission_rows.append(
                Submission(
                    assignment_id=assignment.id,
                    student_id=student.id,
                    submission_text=f"Submission for {assignment.title} by {student.first_name} {student.last_name}.",
                    submitted_at=submitted_at,
                    grade=grade,
                    feedback=feedback,
                    graded_at=graded_at,
                )
            )
            existing_submission_keys.add(submission_key)

    if submission_rows:
        db.session.bulk_save_objects(submission_rows)


def seed_notifications(branch: Branch):
    existing_keys = {(row.target_role, row.message) for row in Notification.query.filter_by(branch_id=branch.id).all()}
    notification_rows = []
    base_time = datetime.utcnow()

    for index, (target_role, message) in enumerate(NOTIFICATION_MESSAGES):
        notification_key = (target_role, message)
        if notification_key in existing_keys:
            continue
        notification_rows.append(
            Notification(
                target_role=target_role,
                message=message,
                branch_id=branch.id,
                created_at=base_time - timedelta(days=index),
            )
        )
        existing_keys.add(notification_key)

    if notification_rows:
        db.session.bulk_save_objects(notification_rows)


def assign_local_guardians(faculty_by_name, students):
    guardian_pool = [
        faculty_by_name["Dr. P. S. Sanjekar"],
        faculty_by_name["Dr. U. M. Patil"],
        faculty_by_name["Prof. A. B. Patil"],
        faculty_by_name["Dr. M. S. Patil"],
        faculty_by_name["Dr. K. D. Chaudhari"],
        faculty_by_name["Prof. K. D. Deore"],
        faculty_by_name["Prof. Surekha Patil"],
        faculty_by_name["Prof. S. K. Bhandare"],
    ]
    for index, student in enumerate(students):
        guardian = guardian_pool[index % len(guardian_pool)]
        if student not in guardian.local_guardian_students:
            guardian.local_guardian_students.append(student)


def seed_leave_requests(students):
    existing_keys = {
        (row.student_id, row.start_date, row.end_date, row.reason)
        for row in LeaveRequest.query.filter(LeaveRequest.student_id.in_([student.id for student in students])).all()
    }
    leave_rows = []
    status_cycle = ("Pending", "Approved", "Rejected")

    for index, student in enumerate(students[:18]):
        start_date = date(2026, 3, 10) + timedelta(days=index)
        end_date = start_date + timedelta(days=index % 3)
        reason = LEAVE_REASONS[index % len(LEAVE_REASONS)]
        status = status_cycle[index % len(status_cycle)]
        leave_key = (student.id, start_date, end_date, reason)
        if leave_key in existing_keys:
            continue

        reviewer = student.local_guardians[0] if student.local_guardians else None
        leave_rows.append(
            LeaveRequest(
                student_id=student.id,
                reason=reason,
                start_date=start_date,
                end_date=end_date,
                status=status,
                reviewed_by_id=reviewer.id if reviewer and status != "Pending" else None,
                reviewed_at=datetime(2026, 3, 9, 11, 0) + timedelta(days=index) if status != "Pending" else None,
                created_at=datetime(2026, 3, 8, 9, 30) + timedelta(days=index),
            )
        )
        existing_keys.add(leave_key)

    if leave_rows:
        db.session.bulk_save_objects(leave_rows)


def seed_calendar_events(branch: Branch):
    try:
        from seed_calendar import CALENDAR_ENTRIES, SEMESTER as CALENDAR_SEMESTER
    except Exception:
        return

    existing_keys = {
        (event.date.isoformat(), event.title, event.type)
        for event in CalendarEvent.query.filter_by(branch_id=branch.id, semester=CALENDAR_SEMESTER).all()
    }
    calendar_rows = []
    for entry in CALENDAR_ENTRIES:
        event_key = (entry["date"], entry["title"], entry["type"])
        if event_key in existing_keys:
            continue
        calendar_rows.append(
            CalendarEvent(
                title=entry["title"],
                date=datetime.strptime(entry["date"], "%Y-%m-%d").date(),
                type=entry["type"],
                branch_id=branch.id,
                semester=CALENDAR_SEMESTER,
            )
        )
        existing_keys.add(event_key)

    if calendar_rows:
        db.session.bulk_save_objects(calendar_rows)


def print_summary(branch, divisions, students, subject_by_code, faculty_by_name):
    faculty_count = User.query.filter_by(role="faculty", branch_id=branch.id).count()
    student_count = User.query.filter_by(role="student", branch_id=branch.id).count()
    timetable_count = Timetable.query.filter_by(branch_id=branch.id).count()
    assignment_count = Assignment.query.join(Subject).filter(Subject.branch_id == branch.id).count()
    exam_count = Exam.query.join(Subject).filter(Subject.branch_id == branch.id).count()
    notification_count = Notification.query.filter_by(branch_id=branch.id).count()

    print(f"Seed complete for branch: {branch.name}")
    print(f"Divisions: {', '.join(division.name for division in divisions.values())}")
    print(f"Faculty: {faculty_count}")
    print(f"Students: {student_count}")
    print(f"Subjects: {len(subject_by_code)}")
    print(f"Timetable rows: {timetable_count}")
    print(f"Assignments: {assignment_count}")
    print(f"Exams: {exam_count}")
    print(f"Notifications: {notification_count}")
    print(f"Default seeded password: {DEFAULT_PASSWORD}")
    print("Faculty accounts:")
    for faculty_name, faculty in faculty_by_name.items():
        print(f"  - {faculty_name} -> {faculty.email}")
    print("HOD account: hod.datascience@academiapro.local")
    print("Admin account: admin@example.com")
    print(f"Student PRNs: {students[0].prn} to {students[-1].prn}")


def seed_database(config_class=Config):
    app = create_app(config_class)
    with app.app_context():
        get_or_create_admin()
        branch = get_or_create_branch()
        divisions = get_or_create_divisions(branch)
        get_or_create_hod(branch)
        faculty_by_name = seed_faculty(branch)
        students_by_division = seed_students(branch, divisions)
        subject_by_code = seed_subjects(branch)
        assign_faculty_to_subjects(faculty_by_name, subject_by_code)
        students = enroll_students(students_by_division, subject_by_code)
        assign_local_guardians(faculty_by_name, students)
        db.session.commit()

        schedule_a, schedule_b = seed_timetables(branch, divisions, subject_by_code, faculty_by_name)
        db.session.commit()

        seed_attendance(students, subject_by_code, schedule_a, schedule_b)
        db.session.commit()

        seed_exams_and_marks(students, subject_by_code, faculty_by_name)
        db.session.commit()

        seed_assignments_and_submissions(students, subject_by_code, faculty_by_name)
        db.session.commit()

        seed_notifications(branch)
        seed_leave_requests(students)
        seed_calendar_events(branch)
        db.session.commit()

        print_summary(branch, divisions, students, subject_by_code, faculty_by_name)


if __name__ == "__main__":
    seed_database()
