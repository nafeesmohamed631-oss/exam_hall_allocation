# Exam Hall & Seating Arrangement Management System

Mini project - **Web Framework using Python** (Flask) + **MongoDB** (embedded documents, CRUD, filter/sort, GridFS media).

Stack: Flask · PyMongo · MongoDB GridFS · ReportLab (PDF) · Flask-Mail (email) · optional Twilio (SMS) · HTML/CSS/JavaScript (no React).

## 1. Setup
```bash
# 1. Install & start MongoDB Community Server (and optionally MongoDB Compass)
# 2. Project setup
python -m venv venv
venv\Scripts\activate          # Windows   |   source venv/bin/activate  (Linux/Mac)
pip install -r requirements.txt
copy .env.example .env         # (cp on Linux/Mac) - edit values if needed
python seed.py                 # OPTIONAL: inserts demo students/exam/halls into MongoDB
python app.py                  # open http://127.0.0.1:5000
```
Admin login (created in the `admins` collection on first run): **admin / admin123** (change in `.env` before first run).
Students use the home page ("Find my seat") with their register number - no login needed.

## 2. Demo flow (viva)
1. Login -> **Exams**: create an exam. **Halls**: add halls *with an image* (stored in GridFS). **Students**: add / edit / delete, filter and sort.
2. **Seatings** -> choose exam -> *Generate*. Students are sorted by register number inside MongoDB and seated hall by hall.
3. Edit a seat (Reassign), remove an allotment, filter by exam / hall / register no.
4. **Exams** -> *PDF* downloads the seating chart; *Notify* sends email (and SMS if Twilio is set).
5. Log out -> home page -> enter a register number -> hall, seat and **hall image from GridFS** are shown.
6. Run `python verify_db.py` for the requirement checklist, then show MongoDB Compass (queries below).

## 3. Requirement -> implementation
| Requirement | Where |
|---|---|
| Embedded documents | `students.exam_details[]` (exam_id, subject, exam_date, start_time, hall_id, seat_no); `halls.image{}` (gridfs_id, filename, content_type, size) |
| CREATE / READ / UPDATE / DELETE | `insert_one/insert_many`, `find/find_one/aggregate`, `update_one/update_many`, `delete_one/delete_many` for students, exams, halls, seatings (`app.py`) |
| Filtering (DB queries) | students by department / exam (`exam_details.exam_id`) / text; exams by date; halls by building; seatings by exam / hall / register prefix |
| Sorting (DB queries) | `.sort()` / `$sort` - name, register no, newest, oldest, capacity, hall/seat |
| Image storage | Flask upload -> `gridfs.GridFS(db, "hall_images").put()` -> `hall_images.files` + `hall_images.chunks` |
| Media reference/metadata | `halls.image.gridfs_id` + filename/content_type/size |
| Media retrieval | `/media/<id>` streams the file from GridFS; shown in Halls page and student result |
| Relationships | `seatings` -> `student_id`, `exam_id`, `hall_id` (ObjectIds); `$lookup` joins; unique indexes prevent double booking |
| Admin management | Dashboard + CRUD pages, upload/replace media, login with hashed password |
| Real data / not-found handling | no hard-coded data; unknown register no -> 404 JSON message; invalid ids -> 404 page |
| PDF / Email / SMS | `exam_pdf` (ReportLab), `exam_notify` (Flask-Mail / Twilio) |

## 4. Verify directly in MongoDB (mongosh / Compass)
```js
use exam_seating_db
db.students.findOne({"exam_details.0": {$exists: true}})        // embedded documents
db.halls.find({}, {hall_name:1, image:1})                        // media reference in hall
db.getCollection("hall_images.files").find()                     // GridFS metadata
db.getCollection("hall_images.chunks").countDocuments()          // GridFS binary chunks
db.seatings.find().sort({register_no:1}).limit(5)                // seating relationships
db.students.find({department:"CSE"}).sort({name:1})              // filter + sort
db.seatings.aggregate([{$lookup:{from:"students",localField:"student_id",foreignField:"_id",as:"s"}}])
```

## 5. Seating algorithm
1. Students (optionally one department) fetched with `.sort("register_no", 1)`.
2. Halls fetched sorted by name; halls already used by another exam at the **same date and start time** are excluded.
3. If total capacity < students, nothing is changed and an error is shown.
4. The previous arrangement of the exam is cleared, then seats `A1, A2 … B1 …` are assigned hall by hall.
5. `seatings` documents are inserted and the embedded `exam_details` entry is pushed into each student (bulk write).

## 6. Email / SMS
Set `MAIL_*` in `.env` (for Gmail use an *App Password*). For SMS: `pip install twilio` and set `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_FROM`; students need a phone number in international format.

## 7. Structure
```
app.py            Flask app: routes, MongoDB queries, GridFS, PDF, email
seed.py           optional demo data inserted into the real DB
verify_db.py      automatic checklist for the mandatory requirements
templates/        Jinja2 pages        static/  style.css, app.js
```
"# exam_hall_allocation" 
