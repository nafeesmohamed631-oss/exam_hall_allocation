"""Optional: insert demo records into the REAL MongoDB database (python seed.py)."""
from datetime import datetime
from app import db

if db.students.count_documents({}):
    raise SystemExit("Database already has students - seed skipped.")

names = ["Arun", "Bala", "Chitra", "Divya", "Elango", "Fathima", "Gokul", "Hari", "Indu", "Jeeva"]
depts = ["CSE", "ECE", "MECH"]
students = [{
    "register_no": f"{depts[i % 3]}{2024000 + i}", "name": f"{names[i % 10]} {chr(65 + i // 10)}",
    "department": depts[i % 3], "year": 2, "email": f"student{i}@example.com", "phone": "",
    "exam_details": [], "created_at": datetime.utcnow()} for i in range(30)]
db.students.insert_many(students)
db.exams.insert_one({"exam_name": "Semester End Exam", "subject": "Web Framework using Python",
                     "exam_date": "2026-11-20", "start_time": "10:00", "duration": 180,
                     "created_at": datetime.utcnow()})
db.halls.insert_many([
    {"hall_name": f"Hall {n}", "building": "Main Block", "rows": 4, "columns": 5, "capacity": 20,
     "image": None, "created_at": datetime.utcnow()} for n in ("A", "B")])
print("Seeded 30 students, 1 exam, 2 halls. Upload hall images from the admin panel.")
