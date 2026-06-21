"""
Face Recognition Attendance System - FastAPI Backend
Originally built during IOCL internship (Tkinter-based) — upgraded here to a
production-style REST API with JWT auth, OpenCV face recognition, and SQLite.
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, date
import sqlite3
import bcrypt
import jwt as pyjwt
import csv
import io
import json

import face_service

DB_PATH = "attendance.db"
SECRET_KEY = "change-this-secret-key-in-production-67890"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

app = FastAPI(title="Face Recognition Attendance System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5174",
                   "http://127.0.0.1:3000", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()


# ---------------- DATABASE ----------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_code TEXT UNIQUE NOT NULL,
            face_images TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            confidence REAL,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            UNIQUE(employee_id, date)
        )
    """)
    conn.commit()
    conn.close()
    print("Database initialized!")


def retrain_from_db():
    """Reload all employee face images from DB and retrain the recognizer."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, face_images FROM employees")
    rows = cur.fetchall()
    conn.close()

    employee_faces = {row["id"]: json.loads(row["face_images"]) for row in rows}
    if employee_faces:
        face_service.train_recognizer(employee_faces)


# ---------------- MODELS ----------------
class AdminRegister(BaseModel):
    email: str
    password: str


class AdminLogin(BaseModel):
    email: str
    password: str


class EmployeeRegister(BaseModel):
    name: str
    employee_code: str
    face_images: List[str]  # base64 encoded images, 1-5 recommended


class MarkAttendanceRequest(BaseModel):
    image: str  # base64 webcam snapshot


# ---------------- AUTH HELPERS ----------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_token(admin_id: int, email: str) -> str:
    payload = {
        "admin_id": admin_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"admin_id": payload["admin_id"], "email": payload["email"]}
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------- STARTUP ----------------
@app.on_event("startup")
def startup():
    init_db()
    retrain_from_db()


# ---------------- AUTH ROUTES ----------------
@app.post("/auth/register", status_code=201)
def register_admin(admin: AdminRegister):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM admins WHERE email = ?", (admin.email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    password_hash = hash_password(admin.password)
    cur.execute("INSERT INTO admins (email, password_hash) VALUES (?, ?)", (admin.email, password_hash))
    conn.commit()
    admin_id = cur.lastrowid
    conn.close()

    token = create_token(admin_id, admin.email)
    return {"access_token": token, "token_type": "bearer", "email": admin.email}


@app.post("/auth/login")
def login_admin(admin: AdminLogin):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, email, password_hash FROM admins WHERE email = ?", (admin.email,))
    row = cur.fetchone()
    conn.close()

    if not row or not verify_password(admin.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(row["id"], row["email"])
    return {"access_token": token, "token_type": "bearer", "email": row["email"]}


# ---------------- EMPLOYEE ROUTES ----------------
@app.post("/employees/register", status_code=201)
def register_employee(emp: EmployeeRegister, current_admin: dict = Depends(get_current_admin)):
    if not emp.face_images:
        raise HTTPException(status_code=400, detail="At least one face image is required")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM employees WHERE employee_code = ?", (emp.employee_code,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Employee code already exists")

    cur.execute(
        "INSERT INTO employees (name, employee_code, face_images) VALUES (?, ?, ?)",
        (emp.name, emp.employee_code, json.dumps(emp.face_images))
    )
    conn.commit()
    employee_id = cur.lastrowid
    conn.close()

    retrain_from_db()  # retrain recognizer with new face data
    return {"id": employee_id, "name": emp.name, "employee_code": emp.employee_code}


@app.get("/employees")
def list_employees(current_admin: dict = Depends(get_current_admin)):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, employee_code, created_at FROM employees")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ---------------- ATTENDANCE ROUTES ----------------
@app.post("/attendance/mark")
def mark_attendance(req: MarkAttendanceRequest):
    employee_id, confidence = face_service.recognize_face(req.image)

    if employee_id is None:
        return {
            "matched": False,
            "message": "No matching employee found",
            "confidence": confidence,
        }

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, employee_code FROM employees WHERE id = ?", (employee_id,))
    emp = cur.fetchone()
    if not emp:
        conn.close()
        return {"matched": False, "message": "Employee record not found"}

    today = date.today().isoformat()
    now_time = datetime.now().strftime("%H:%M:%S")

    cur.execute(
        "SELECT id FROM attendance_logs WHERE employee_id = ? AND date = ?",
        (employee_id, today)
    )
    already_marked = cur.fetchone()

    if already_marked:
        conn.close()
        return {
            "matched": True,
            "already_marked": True,
            "name": emp["name"],
            "employee_code": emp["employee_code"],
            "message": f"{emp['name']} already marked present today",
        }

    cur.execute(
        "INSERT INTO attendance_logs (employee_id, date, time, confidence) VALUES (?, ?, ?, ?)",
        (employee_id, today, now_time, confidence)
    )
    conn.commit()
    conn.close()

    return {
        "matched": True,
        "already_marked": False,
        "name": emp["name"],
        "employee_code": emp["employee_code"],
        "time": now_time,
        "confidence": confidence,
        "message": f"Attendance marked for {emp['name']}",
    }


@app.get("/attendance/report")
def attendance_report(report_date: Optional[str] = None, current_admin: dict = Depends(get_current_admin)):
    target_date = report_date or date.today().isoformat()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, employee_code FROM employees")
    all_employees = cur.fetchall()

    cur.execute(
        """SELECT employee_id, time, confidence FROM attendance_logs WHERE date = ?""",
        (target_date,)
    )
    present_rows = {r["employee_id"]: r for r in cur.fetchall()}
    conn.close()

    present = []
    absent = []
    for emp in all_employees:
        if emp["id"] in present_rows:
            log = present_rows[emp["id"]]
            present.append({
                "name": emp["name"],
                "employee_code": emp["employee_code"],
                "time": log["time"],
                "confidence": log["confidence"],
            })
        else:
            absent.append({"name": emp["name"], "employee_code": emp["employee_code"]})

    return {
        "date": target_date,
        "present_count": len(present),
        "absent_count": len(absent),
        "total_employees": len(all_employees),
        "present": present,
        "absent": absent,
    }


@app.get("/attendance/export")
def export_csv(report_date: Optional[str] = None, current_admin: dict = Depends(get_current_admin)):
    target_date = report_date or date.today().isoformat()
    report = attendance_report(report_date=target_date, current_admin=current_admin)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Employee Code", "Status", "Time", "Confidence"])
    for p in report["present"]:
        writer.writerow([p["name"], p["employee_code"], "Present", p["time"], p["confidence"]])
    for a in report["absent"]:
        writer.writerow([a["name"], a["employee_code"], "Absent", "-", "-"])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_{target_date}.csv"}
    )


@app.get("/")
def root():
    return {"message": "Face Recognition Attendance System API", "docs": "/docs"}
