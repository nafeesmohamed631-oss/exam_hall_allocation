"""Exam Hall and Seating Arrangement Management System
Flask + MongoDB (PyMongo) + GridFS + ReportLab + Flask-Mail
"""
import io
import os
import re
from datetime import datetime
from functools import wraps
from itertools import groupby

import gridfs
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from flask import (Flask, abort, flash, jsonify, redirect, render_template,
                   request, send_file, session, url_for)
from flask_mail import Mail, Message
from pymongo import ASCENDING, MongoClient, UpdateOne
from pymongo.errors import DuplicateKeyError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB upload limit
    MAIL_SERVER=os.getenv("MAIL_SERVER", ""),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "true").lower() == "true",
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME"),
)
mail = Mail(app)

# ----------------------------------------------------------------- database
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"),
                     serverSelectionTimeoutMS=5000)
db = client[os.getenv("DB_NAME", "exam_seating_db")]
fs = gridfs.GridFS(db, collection="hall_images")   # GridFS bucket "hall_images"

ALLOWED_IMAGES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def init_db():
    """Create indexes (enforce integrity) and the default admin account."""
    db.students.create_index("register_no", unique=True)
    db.halls.create_index("hall_name", unique=True)
    db.seatings.create_index([("exam_id", 1), ("hall_id", 1), ("seat_no", 1)], unique=True)
    db.seatings.create_index([("exam_id", 1), ("student_id", 1)], unique=True)
    db.admins.create_index("username", unique=True)
    if db.admins.count_documents({}) == 0:
        db.admins.insert_one({
            "username": os.getenv("ADMIN_USERNAME", "admin"),
            "password_hash": generate_password_hash(os.getenv("ADMIN_PASSWORD", "admin123")),
            "created_at": datetime.utcnow(),
        })


# ------------------------------------------------------------------ helpers
def oid(value):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        abort(404)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def form_int(name, default=0):
    try:
        return int(request.form.get(name, default))
    except (TypeError, ValueError):
        return default


def seat_pos(seat):
    """'B3' -> (1, 3) ; returns None if malformed."""
    m = re.fullmatch(r"([A-Z])(\d+)", seat.strip().upper())
    return (ord(m.group(1)) - 65, int(m.group(2))) if m else None


def seat_in_hall(hall, seat):
    pos = seat_pos(seat)
    return bool(pos) and pos[0] < hall["rows"] and 1 <= pos[1] <= hall["columns"]


def seat_slots(halls):
    for h in halls:
        for r in range(h["rows"]):
            for c in range(1, h["columns"] + 1):
                yield h, r, c


def seating_pipeline(match, sort, limit=None):
    """Aggregation joining seatings -> students / exams / halls via ObjectIds."""
    p = [{"$match": match},
         {"$lookup": {"from": "students", "localField": "student_id", "foreignField": "_id", "as": "student"}},
         {"$lookup": {"from": "exams", "localField": "exam_id", "foreignField": "_id", "as": "exam"}},
         {"$lookup": {"from": "halls", "localField": "hall_id", "foreignField": "_id", "as": "hall"}},
         {"$unwind": "$student"}, {"$unwind": "$exam"}, {"$unwind": "$hall"},
         {"$sort": sort}]
    if limit:
        p.append({"$limit": limit})
    return p


def clear_exam(exam_id):
    """Remove all allotments of an exam (seatings + embedded exam_details)."""
    db.seatings.delete_many({"exam_id": exam_id})
    db.students.update_many({"exam_details.exam_id": exam_id},
                            {"$pull": {"exam_details": {"exam_id": exam_id}}})


def store_image(file, hall_name):
    """Upload an image to GridFS and return the metadata embedded in the hall."""
    if not file or not file.filename:
        return None
    if file.mimetype not in ALLOWED_IMAGES:
        raise ValueError("Only PNG, JPEG, GIF or WEBP images are allowed.")
    data = file.read()
    fid = fs.put(data, filename=file.filename, content_type=file.mimetype, hall_name=hall_name)
    return {"gridfs_id": fid, "filename": file.filename, "content_type": file.mimetype,
            "size": len(data), "uploaded_at": datetime.utcnow()}


def delete_image(image):
    if image and image.get("gridfs_id"):
        fs.delete(image["gridfs_id"])


@app.errorhandler(404)
@app.errorhandler(413)
def error_page(e):
    msg = "File too large (max 5 MB)." if e.code == 413 else "The requested record or page does not exist."
    return render_template("error.html", message=msg, code=e.code), e.code


# -------------------------------------------------------------- public side
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/lookup/<reg>")
def api_lookup(reg):
    student = db.students.find_one({"register_no": reg.strip().upper()})
    if not student:
        return jsonify(error="No student found with this register number."), 404
    rows = db.seatings.aggregate(seating_pipeline({"student_id": student["_id"]}, {"exam.exam_date": 1}))
    result = []
    for r in rows:
        img = r["hall"].get("image")
        result.append({
            "exam_name": r["exam"]["exam_name"], "subject": r["exam"]["subject"],
            "exam_date": r["exam"]["exam_date"], "start_time": r["exam"]["start_time"],
            "duration": r["exam"]["duration"], "hall_name": r["hall"]["hall_name"],
            "building": r["hall"].get("building", ""), "seat_no": r["seat_no"],
            "image_url": url_for("media", file_id=str(img["gridfs_id"])) if img else None,
        })
    return jsonify(student={"register_no": student["register_no"], "name": student["name"],
                            "department": student["department"], "year": student["year"]},
                   allotments=result)


@app.route("/media/<file_id>")
def media(file_id):
    """Stream a file out of MongoDB GridFS."""
    try:
        f = fs.get(oid(file_id))
    except gridfs.errors.NoFile:
        abort(404)
    return send_file(io.BytesIO(f.read()), mimetype=f.content_type, download_name=f.filename)


# --------------------------------------------------------------------- auth
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        admin = db.admins.find_one({"username": request.form.get("username", "").strip()})
        if admin and check_password_hash(admin["password_hash"], request.form.get("password", "")):
            session["admin"] = admin["username"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- dashboard
@app.route("/admin")
@login_required
def dashboard():
    stats = {n: db[n].count_documents({}) for n in ("students", "exams", "halls", "seatings")}
    stats["media_files"] = db["hall_images.files"].count_documents({})
    recent = list(db.seatings.aggregate(seating_pipeline({}, {"assigned_at": -1}, limit=8)))
    return render_template("dashboard.html", stats=stats, recent=recent)


# ----------------------------------------------------------------- students
STUDENT_SORTS = {"reg": ("Register no (A-Z)", [("register_no", 1)]),
                 "name": ("Name (A-Z)", [("name", 1)]),
                 "newest": ("Newest first", [("created_at", -1)]),
                 "oldest": ("Oldest first", [("created_at", 1)])}


@app.route("/admin/students")
@login_required
def students_page():
    q = {}
    dept, exam, search = request.args.get("department"), request.args.get("exam"), request.args.get("q", "").strip()
    if dept:
        q["department"] = dept
    if exam:
        q["exam_details.exam_id"] = oid(exam)            # query inside embedded documents
    if search:
        rx = {"$regex": re.escape(search), "$options": "i"}
        q["$or"] = [{"name": rx}, {"register_no": rx}]
    sort = request.args.get("sort", "reg")
    items = list(db.students.find(q).sort(STUDENT_SORTS.get(sort, STUDENT_SORTS["reg"])[1]))
    return render_template("students.html", items=items, sort=sort,
                           sorts=[(k, v[0]) for k, v in STUDENT_SORTS.items()],
                           departments=sorted(db.students.distinct("department")),
                           exams=list(db.exams.find().sort("exam_date", 1)),
                           halls={h["_id"]: h for h in db.halls.find()})


def student_from_form():
    f = request.form
    return {"register_no": f["register_no"].strip().upper(), "name": f["name"].strip(),
            "department": f["department"].strip().upper(), "year": form_int("year", 1),
            "email": f.get("email", "").strip().lower(), "phone": f.get("phone", "").strip()}


@app.route("/admin/students/add", methods=["POST"])
@login_required
def student_add():
    doc = student_from_form()
    doc.update(exam_details=[], created_at=datetime.utcnow())
    try:
        db.students.insert_one(doc)                                   # CREATE
        flash(f"Student {doc['register_no']} added.", "success")
    except DuplicateKeyError:
        flash("A student with this register number already exists.", "error")
    return redirect(url_for("students_page"))


@app.route("/admin/students/<sid>/edit", methods=["POST"])
@login_required
def student_edit(sid):
    doc = student_from_form()
    try:
        res = db.students.update_one({"_id": oid(sid)}, {"$set": doc})  # UPDATE
    except DuplicateKeyError:
        flash("That register number is already used by another student.", "error")
        return redirect(url_for("students_page"))
    if not res.matched_count:
        abort(404)
    db.seatings.update_many({"student_id": oid(sid)}, {"$set": {"register_no": doc["register_no"]}})
    flash("Student updated.", "success")
    return redirect(url_for("students_page"))


@app.route("/admin/students/<sid>/delete", methods=["POST"])
@login_required
def student_delete(sid):
    db.seatings.delete_many({"student_id": oid(sid)})
    res = db.students.delete_one({"_id": oid(sid)})                    # DELETE
    flash("Student deleted." if res.deleted_count else "Student not found.", "success" if res.deleted_count else "error")
    return redirect(url_for("students_page"))


# -------------------------------------------------------------------- exams
EXAM_SORTS = {"oldest": ("Oldest first", [("exam_date", 1), ("start_time", 1)]),
              "newest": ("Newest first", [("exam_date", -1), ("start_time", -1)]),
              "name": ("Name (A-Z)", [("exam_name", 1)])}


@app.route("/admin/exams")
@login_required
def exams_page():
    q = {}
    if request.args.get("date"):
        q["exam_date"] = request.args["date"]
    sort = request.args.get("sort", "oldest")
    items = list(db.exams.find(q).sort(EXAM_SORTS.get(sort, EXAM_SORTS["oldest"])[1]))
    counts = {r["_id"]: r["n"] for r in db.seatings.aggregate([{"$group": {"_id": "$exam_id", "n": {"$sum": 1}}}])}
    return render_template("exams.html", items=items, counts=counts, sort=sort,
                           sorts=[(k, v[0]) for k, v in EXAM_SORTS.items()])


def exam_from_form():
    f = request.form
    return {"exam_name": f["exam_name"].strip(), "subject": f["subject"].strip(),
            "exam_date": f["exam_date"], "start_time": f["start_time"], "duration": form_int("duration", 180)}


@app.route("/admin/exams/add", methods=["POST"])
@login_required
def exam_add():
    doc = exam_from_form()
    doc["created_at"] = datetime.utcnow()
    db.exams.insert_one(doc)
    flash("Exam created.", "success")
    return redirect(url_for("exams_page"))


@app.route("/admin/exams/<eid>/edit", methods=["POST"])
@login_required
def exam_edit(eid):
    doc = exam_from_form()
    if not db.exams.update_one({"_id": oid(eid)}, {"$set": doc}).matched_count:
        abort(404)
    # keep embedded copies in students in sync
    db.students.update_many(
        {"exam_details.exam_id": oid(eid)},
        {"$set": {"exam_details.$.subject": doc["subject"], "exam_details.$.exam_date": doc["exam_date"],
                  "exam_details.$.start_time": doc["start_time"]}})   # positional operator: matched array element
    flash("Exam updated.", "success")
    return redirect(url_for("exams_page"))


@app.route("/admin/exams/<eid>/delete", methods=["POST"])
@login_required
def exam_delete(eid):
    clear_exam(oid(eid))
    db.exams.delete_one({"_id": oid(eid)})
    flash("Exam and its seating arrangement deleted.", "success")
    return redirect(url_for("exams_page"))


@app.route("/admin/exams/<eid>/pdf")
@login_required
def exam_pdf(eid):
    exam = db.exams.find_one({"_id": oid(eid)}) or abort(404)
    rows = list(db.seatings.aggregate(seating_pipeline(
        {"exam_id": exam["_id"]}, {"hall.hall_name": 1, "row": 1, "col": 1})))
    if not rows:
        flash("Generate the seating arrangement before downloading the PDF.", "error")
        return redirect(url_for("exams_page"))
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Seating Arrangement")
    story = []
    for i, (_, group) in enumerate(groupby(rows, key=lambda r: r["hall"]["_id"])):
        group = list(group)
        hall = group[0]["hall"]
        if i:
            story.append(PageBreak())
        story += [Paragraph(f"Seating Arrangement - {exam['exam_name']}", styles["Title"]),
                  Paragraph(f"{exam['subject']} | {exam['exam_date']} {exam['start_time']} | "
                            f"{exam['duration']} min", styles["Normal"]),
                  Paragraph(f"<b>Hall:</b> {hall['hall_name']} ({hall.get('building', '')})", styles["Heading3"]),
                  Spacer(1, 8)]
        data = [["Seat", "Register No", "Name", "Department"]] + [
            [r["seat_no"], r["register_no"], r["student"]["name"], r["student"]["department"]] for r in group]
        t = Table(data, repeatRows=1, colWidths=[50, 110, 220, 90])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                               ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2ff")])]))
        story.append(t)
    doc.build(story)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                     download_name=f"seating_{exam['exam_name'].replace(' ', '_')}.pdf")


@app.route("/admin/exams/<eid>/notify", methods=["POST"])
@login_required
def exam_notify(eid):
    exam = db.exams.find_one({"_id": oid(eid)}) or abort(404)
    email_on = bool(app.config["MAIL_SERVER"])
    sms_on = all(os.getenv(k) for k in ("TWILIO_SID", "TWILIO_TOKEN", "TWILIO_FROM"))
    if not (email_on or sms_on):
        flash("Email/SMS is not configured. Set MAIL_SERVER (and credentials) in .env.", "error")
        return redirect(url_for("exams_page"))
    rows = list(db.seatings.aggregate(seating_pipeline({"exam_id": exam["_id"]}, {"register_no": 1})))
    sms_client = None
    if sms_on:
        try:
            from twilio.rest import Client
            sms_client = Client(os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"))
        except ImportError:
            flash("Install 'twilio' to enable SMS.", "error")
    sent = failed = 0
    for r in rows:
        s, h = r["student"], r["hall"]
        text = (f"Dear {s['name']}, your {exam['subject']} exam ({exam['exam_name']}) is on "
                f"{exam['exam_date']} at {exam['start_time']}. Hall: {h['hall_name']} "
                f"({h.get('building', '')}), Seat: {r['seat_no']}.")
        try:
            if email_on and s.get("email"):
                mail.send(Message(f"Exam seating: {exam['subject']}", recipients=[s["email"]], body=text))
                sent += 1
            if sms_client and s.get("phone"):
                sms_client.messages.create(to=s["phone"], from_=os.getenv("TWILIO_FROM"), body=text)
                sent += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            app.logger.warning("Notification failed for %s: %s", s["register_no"], exc)
    flash(f"Notifications sent: {sent}, failed: {failed}.", "success" if not failed else "error")
    return redirect(url_for("exams_page"))


# -------------------------------------------------------------------- halls
HALL_SORTS = {"name": ("Name (A-Z)", [("hall_name", 1)]),
              "capacity": ("Capacity (high-low)", [("capacity", -1)]),
              "building": ("Building (A-Z)", [("building", 1), ("hall_name", 1)])}


@app.route("/admin/halls")
@login_required
def halls_page():
    q = {"building": request.args["building"]} if request.args.get("building") else {}
    sort = request.args.get("sort", "name")
    items = list(db.halls.find(q).sort(HALL_SORTS.get(sort, HALL_SORTS["name"])[1]))
    return render_template("halls.html", items=items, sort=sort,
                           sorts=[(k, v[0]) for k, v in HALL_SORTS.items()],
                           buildings=sorted(b for b in db.halls.distinct("building") if b))


def hall_from_form():
    f = request.form
    rows, cols = max(1, min(26, form_int("rows", 5))), max(1, form_int("columns", 6))
    return {"hall_name": f["hall_name"].strip(), "building": f.get("building", "").strip(),
            "rows": rows, "columns": cols, "capacity": rows * cols}


@app.route("/admin/halls/add", methods=["POST"])
@login_required
def hall_add():
    doc = hall_from_form()
    try:
        doc["image"] = store_image(request.files.get("image"), doc["hall_name"])  # GridFS upload
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("halls_page"))
    doc["created_at"] = datetime.utcnow()
    try:
        db.halls.insert_one(doc)
        flash("Hall created.", "success")
    except DuplicateKeyError:
        delete_image(doc["image"])
        flash("A hall with this name already exists.", "error")
    return redirect(url_for("halls_page"))


@app.route("/admin/halls/<hid>/edit", methods=["POST"])
@login_required
def hall_edit(hid):
    hall = db.halls.find_one({"_id": oid(hid)}) or abort(404)
    doc = hall_from_form()
    if (doc["rows"], doc["columns"]) != (hall["rows"], hall["columns"]) and \
            db.seatings.count_documents({"hall_id": hall["_id"]}):
        flash("Cannot change the layout while seats are allotted in this hall.", "error")
        return redirect(url_for("halls_page"))
    try:
        new_img = store_image(request.files.get("image"), doc["hall_name"])
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("halls_page"))
    if new_img:
        delete_image(hall.get("image"))     # replace old media in GridFS
        doc["image"] = new_img
    try:
        db.halls.update_one({"_id": hall["_id"]}, {"$set": doc})
        flash("Hall updated.", "success")
    except DuplicateKeyError:
        if new_img:
            delete_image(new_img)
        flash("A hall with this name already exists.", "error")
    return redirect(url_for("halls_page"))


@app.route("/admin/halls/<hid>/delete", methods=["POST"])
@login_required
def hall_delete(hid):
    hall = db.halls.find_one({"_id": oid(hid)}) or abort(404)
    db.seatings.delete_many({"hall_id": hall["_id"]})
    db.students.update_many({"exam_details.hall_id": hall["_id"]},
                            {"$pull": {"exam_details": {"hall_id": hall["_id"]}}})
    delete_image(hall.get("image"))
    db.halls.delete_one({"_id": hall["_id"]})
    flash("Hall, its image and its allotments were deleted.", "success")
    return redirect(url_for("halls_page"))


# ----------------------------------------------------------------- seatings
SEAT_SORTS = {"reg": ("Register no", {"register_no": 1}),
              "seat": ("Hall / seat", {"hall.hall_name": 1, "row": 1, "col": 1}),
              "newest": ("Newest first", {"assigned_at": -1}),
              "oldest": ("Oldest first", {"assigned_at": 1})}


@app.route("/admin/seatings")
@login_required
def seatings_page():
    match = {}
    a = request.args
    if a.get("exam"):
        match["exam_id"] = oid(a["exam"])
    if a.get("hall"):
        match["hall_id"] = oid(a["hall"])
    if a.get("q", "").strip():
        match["register_no"] = {"$regex": "^" + re.escape(a["q"].strip().upper())}
    sort = a.get("sort", "seat")
    items = list(db.seatings.aggregate(seating_pipeline(match, SEAT_SORTS.get(sort, SEAT_SORTS["seat"])[1])))
    return render_template("seatings.html", items=items, sort=sort,
                           sorts=[(k, v[0]) for k, v in SEAT_SORTS.items()],
                           exams=list(db.exams.find().sort("exam_date", 1)),
                           halls=list(db.halls.find().sort("hall_name", 1)),
                           departments=sorted(db.students.distinct("department")))


@app.route("/admin/seatings/generate", methods=["POST"])
@login_required
def seatings_generate():
    exam = db.exams.find_one({"_id": oid(request.form.get("exam_id"))}) or abort(404)
    department = request.form.get("department", "").strip()
    chosen = [oid(h) for h in request.form.getlist("hall_ids")]

    # students sorted by MongoDB
    students = list(db.students.find({"department": department} if department else {})
                    .sort("register_no", ASCENDING))
    # halls already used by another exam in the same date/time slot are unavailable
    clash = [e["_id"] for e in db.exams.find({"_id": {"$ne": exam["_id"]}, "exam_date": exam["exam_date"],
                                              "start_time": exam["start_time"]})]
    busy = db.seatings.distinct("hall_id", {"exam_id": {"$in": clash}})
    hall_q = {"_id": {"$nin": busy}}
    if chosen:
        hall_q["_id"]["$in"] = chosen
    halls = list(db.halls.find(hall_q).sort("hall_name", ASCENDING))

    capacity = sum(h["capacity"] for h in halls)
    if not students:
        flash("No students match the selection.", "error")
    elif capacity < len(students):
        flash(f"Not enough capacity: {len(students)} students but only {capacity} seats in available halls.", "error")
    else:
        clear_exam(exam["_id"])
        now = datetime.utcnow()
        seatings, ops = [], []
        for s, (h, r, c) in zip(students, seat_slots(halls)):
            seat = f"{chr(65 + r)}{c}"
            seatings.append({"exam_id": exam["_id"], "hall_id": h["_id"], "student_id": s["_id"],
                             "register_no": s["register_no"], "seat_no": seat, "row": r, "col": c,
                             "assigned_at": now})
            ops.append(UpdateOne({"_id": s["_id"]}, {"$push": {"exam_details": {   # embedded document
                "exam_id": exam["_id"], "subject": exam["subject"], "exam_date": exam["exam_date"],
                "start_time": exam["start_time"], "hall_id": h["_id"], "seat_no": seat}}}))
        db.seatings.insert_many(seatings)
        db.students.bulk_write(ops)
        used = len({s["hall_id"] for s in seatings})
        flash(f"Seated {len(seatings)} students in {used} hall(s).", "success")
    return redirect(url_for("seatings_page", exam=exam["_id"]))


@app.route("/admin/seatings/<sid>/edit", methods=["POST"])
@login_required
def seating_edit(sid):
    seating = db.seatings.find_one({"_id": oid(sid)}) or abort(404)
    hall = db.halls.find_one({"_id": oid(request.form.get("hall_id"))}) or abort(404)
    seat = request.form.get("seat_no", "").strip().upper()
    if not seat_in_hall(hall, seat):
        flash(f"Seat {seat} does not exist in {hall['hall_name']} ({hall['rows']}x{hall['columns']}).", "error")
        return redirect(request.referrer or url_for("seatings_page"))
    r, c = seat_pos(seat)
    try:
        db.seatings.update_one({"_id": seating["_id"]},
                               {"$set": {"hall_id": hall["_id"], "seat_no": seat, "row": r, "col": c}})
    except DuplicateKeyError:
        flash(f"Seat {seat} in {hall['hall_name']} is already taken for this exam.", "error")
        return redirect(request.referrer or url_for("seatings_page"))
    db.students.update_one({"_id": seating["student_id"], "exam_details.exam_id": seating["exam_id"]},
                           {"$set": {"exam_details.$.hall_id": hall["_id"], "exam_details.$.seat_no": seat}})
    flash("Seat reassigned.", "success")
    return redirect(request.referrer or url_for("seatings_page"))


@app.route("/admin/seatings/<sid>/delete", methods=["POST"])
@login_required
def seating_delete(sid):
    seating = db.seatings.find_one({"_id": oid(sid)}) or abort(404)
    db.seatings.delete_one({"_id": seating["_id"]})
    db.students.update_one({"_id": seating["student_id"]},
                           {"$pull": {"exam_details": {"exam_id": seating["exam_id"]}}})
    flash("Allotment removed.", "success")
    return redirect(request.referrer or url_for("seatings_page"))


try:
    init_db()
except Exception as exc:  # noqa: BLE001
    print(f"[WARN] Could not initialise MongoDB: {exc}\nIs mongod running and MONGO_URI correct?")

if __name__ == "__main__":
    app.run(debug=True)
