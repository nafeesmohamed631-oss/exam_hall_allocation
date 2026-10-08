"""Demo seed script for MongoDB with nested/embedded document architecture."""
from datetime import datetime
from app import db, clear_exam, seat_slots

# Clear existing sample data for fresh seeded state
db.students.delete_many({})
db.exams.delete_many({})
db.halls.delete_many({})
db.seatings.delete_many({})

names = ["Arun", "Bala", "Chitra", "Divya", "Elango", "Fathima", "Gokul", "Hari", "Indu", "Jeeva"]
depts = ["CSE", "ECE", "MECH"]

# 1. Seed Students with Nested subdocuments (academic, contact, exam_details)
students = []
for i in range(30):
    d = depts[i % 3]
    students.append({
        "register_no": f"{d}202400{i+1:02d}",
        "name": f"{names[i % 10]} {chr(65 + (i // 10))}",
        # Nested subdocument: academic
        "academic": {
            "department": d,
            "year": 2,
            "semester": 4
        },
        # Nested subdocument: contact
        "contact": {
            "email": f"student{i+1}@example.com",
            "phone": f"+91 98765{i+10000}"
        },
        "department": d,
        "year": 2,
        "email": f"student{i+1}@example.com",
        "phone": f"+91 98765{i+10000}",
        # Embedded document array: exam_details
        "exam_details": [],
        "created_at": datetime.utcnow()
    })

inserted_students = db.students.insert_many(students)
student_ids = inserted_students.inserted_ids

# 2. Seed Examination with Nested subdocument (schedule)
exam_doc = {
    "exam_name": "Semester End Exam",
    "subject": "Web Framework using Python",
    # Nested subdocument: schedule
    "schedule": {
        "exam_date": "2026-11-20",
        "start_time": "10:00",
        "duration": 180
    },
    "exam_date": "2026-11-20",
    "start_time": "10:00",
    "duration": 180,
    "created_at": datetime.utcnow()
}
exam_id = db.exams.insert_one(exam_doc).inserted_id

# 3. Seed Examination Halls with Nested subdocument (layout)
halls = [
    {
        "hall_name": "Hall A",
        "building": "Main Block",
        # Nested subdocument: layout
        "layout": {"rows": 4, "columns": 5, "capacity": 20},
        "rows": 4,
        "columns": 5,
        "capacity": 20,
        "image": None,
        "created_at": datetime.utcnow()
    },
    {
        "hall_name": "Hall B",
        "building": "Science Block",
        # Nested subdocument: layout
        "layout": {"rows": 4, "columns": 5, "capacity": 20},
        "rows": 4,
        "columns": 5,
        "capacity": 20,
        "image": None,
        "created_at": datetime.utcnow()
    }
]
inserted_halls = db.halls.insert_many(halls)
hall_docs = list(db.halls.find({"_id": {"$in": inserted_halls.inserted_ids}}))

# 4. Generate Initial Seating & Populate Embedded Documents (exam_details in students)
all_students = list(db.students.find().sort("register_no", 1))
seatings = []
now = datetime.utcnow()

for s, (h, r, c) in zip(all_students, seat_slots(hall_docs)):
    seat = f"{chr(65 + r)}{c}"
    s_dept = s.get("academic", {}).get("department", "CSE")
    
    # Seating record with nested student_details and seat_info
    seatings.append({
        "exam_id": exam_id,
        "hall_id": h["_id"],
        "student_id": s["_id"],
        "register_no": s["register_no"],
        "seat_no": seat,
        "row": r,
        "col": c,
        "student_details": {
            "register_no": s["register_no"],
            "name": s["name"],
            "department": s_dept
        },
        "seat_info": {
            "seat_no": seat,
            "row": r,
            "col": c
        },
        "assigned_at": now
    })

    # Embedded exam_details subdocument pushed directly to student document
    db.students.update_one(
        {"_id": s["_id"]},
        {"$push": {"exam_details": {
            "exam_id": exam_id,
            "exam_name": exam_doc["exam_name"],
            "subject": exam_doc["subject"],
            "exam_date": exam_doc["schedule"]["exam_date"],
            "start_time": exam_doc["schedule"]["start_time"],
            "duration": exam_doc["schedule"]["duration"],
            "hall_id": h["_id"],
            "hall_name": h["hall_name"],
            "building": h["building"],
            "seat_no": seat,
            "row": r,
            "col": c,
            "assigned_at": now
        }}}
    )

db.seatings.insert_many(seatings)
print(f"Successfully seeded {len(students)} students with nested documents & populated exam_details, 1 exam, 2 halls, and {len(seatings)} seatings!")
