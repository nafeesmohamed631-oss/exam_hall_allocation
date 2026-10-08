"""Requirement #10 - verify every mandatory requirement against the real database.
Run:  python verify_db.py
"""
from datetime import datetime
from app import db, fs

ok_all = True


def check(label, ok, detail=""):
    global ok_all
    ok_all &= bool(ok)
    print(("  \u2713 " if ok else "  \u2717 ") + label + (f"  [{detail}]" if detail else ""))


print("1. Embedded documents")
s = db.students.find_one({"exam_details.0": {"$exists": True}})
check("student with embedded exam_details exists", s, s["register_no"] if s else "run seating generation first")
if s:
    check("embedded doc has exam_id, hall_id, seat_no", all(k in s["exam_details"][0] for k in ("exam_id", "hall_id", "seat_no")))

print("2/6. CRUD with real queries (temporary collection)")
t = db["_verify_tmp"]
r = t.insert_one({"x": 1, "at": datetime.utcnow()})
check("CREATE insert_one", t.count_documents({"_id": r.inserted_id}) == 1)
check("READ find_one", t.find_one({"_id": r.inserted_id})["x"] == 1)
t.update_one({"_id": r.inserted_id}, {"$set": {"x": 2}})
check("UPDATE update_one", t.find_one({"_id": r.inserted_id})["x"] == 2)
t.delete_one({"_id": r.inserted_id})
check("DELETE delete_one", t.count_documents({"_id": r.inserted_id}) == 0)
t.drop()

print("3. Filter / sort in the database")
regs = [x["register_no"] for x in db.students.find().sort("register_no", 1)]
check("sort by register_no (DB .sort)", regs == sorted(regs), f"{len(regs)} students")
depts = db.students.distinct("department")
if depts:
    n = db.students.count_documents({"department": depts[0]})
    check("filter by department (DB query)", n > 0, f"{depts[0]}: {n}")

print("4/5. Media stored in GridFS, referenced from halls, retrievable")
halls = list(db.halls.find({"image": {"$ne": None}}))
check("at least one hall has an image", halls, "upload one in the admin panel" if not halls else f"{len(halls)} hall(s)")
for h in halls:
    img = h["image"]
    exists = fs.exists(img["gridfs_id"])
    check(f"{h['hall_name']}: GridFS file exists", exists, img["filename"])
    if exists:
        data = fs.get(img["gridfs_id"]).read()
        check(f"{h['hall_name']}: bytes retrievable & size matches metadata", len(data) == img["size"], f"{len(data)} bytes")

print("7/8. Relationships valid (ObjectId references)")
bad = 0
for sg in db.seatings.find():
    st = db.students.find_one({"_id": sg["student_id"]})
    emb = next((d for d in (st or {}).get("exam_details", []) if d["exam_id"] == sg["exam_id"]), None)
    if not (st and db.exams.count_documents({"_id": sg["exam_id"]}) and db.halls.count_documents({"_id": sg["hall_id"]})
            and emb and emb["seat_no"] == sg["seat_no"] and emb["hall_id"] == sg["hall_id"]):
        bad += 1
check("every seating -> student/exam/hall exist and embedded copy matches", bad == 0,
      f"{db.seatings.count_documents({})} seatings, {bad} broken")
check("no orphan GridFS files", all(db.halls.count_documents({"image.gridfs_id": f["_id"]}) for f in db["hall_images.files"].find()))

print("\nRESULT:", "ALL CHECKS PASSED" if ok_all else "SOME CHECKS FAILED (see \u2717 above)")
