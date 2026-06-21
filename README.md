# 🎯 Face Recognition Attendance System

A production-style upgrade of an attendance system originally built during an **Indian Oil Corporation Limited (IOCL)** internship (Tkinter desktop app). This version replaces the desktop GUI with a **FastAPI REST backend**, **OpenCV face recognition**, **JWT-secured admin routes**, and a **React dashboard**.

![Status](https://img.shields.io/badge/status-working-brightgreen)
![Tests](https://img.shields.io/badge/tests-10%20passing-brightgreen)

## ✨ Features

- 🪪 **Employee Registration** — capture face photos via webcam, stored securely
- 📷 **Live Face Recognition** — OpenCV LBPH recognizer matches webcam snapshots to registered employees
- 🔐 **JWT Admin Auth** — registration and reports are admin-protected; attendance marking is kiosk-mode (no login needed)
- 📊 **Live Dashboard** — present/absent counts, auto-refreshing every 5s
- 📥 **CSV Export** — download daily attendance report
- 🚫 **Duplicate Prevention** — one attendance mark per employee per day
- ✅ **Tested** — 10 Pytest tests covering auth, registration, and attendance logic

## 🧠 How Face Recognition Works

```
Registration:
  Webcam Photo(s) → Grayscale → Haar Cascade Face Detection
       → Crop & Resize to 200x200 → Store as training sample

Recognition (Attendance Marking):
  Webcam Snapshot → Face Detection → LBPH Predict
       → Match found (confidence below threshold)? → Mark Present
       → No match? → Reject, ask to retry
```

**Why OpenCV LBPH instead of `face_recognition`/`dlib`?** The popular `face_recognition` library depends on `dlib`, which requires a C++ compiler and CMake to install — this fails often on Windows and fresh macOS setups. OpenCV's built-in LBPH recognizer (`opencv-contrib-python`) installs via plain `pip` in seconds and is more than sufficient for a controlled, single-organization attendance use case.

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, WebRTC (`getUserMedia`) for webcam |
| Backend | FastAPI, Pydantic v2 |
| Face Recognition | OpenCV (Haar Cascade + LBPH Recognizer) |
| Auth | JWT (PyJWT), bcrypt |
| Database | SQLite (raw, no ORM) |
| Testing | Pytest, unittest.mock (face recognition mocked in CI) |
| DevOps | Docker, docker-compose |

## 🚀 Quickstart

### Option 1 — Docker

```bash
docker-compose up
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5174
- API docs: http://localhost:8000/docs

### Option 2 — Run locally

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5174 — allow camera access when prompted.

## 🧪 Running Tests

```bash
cd backend
pip install pytest httpx
pytest test_main.py -v
```

Face recognition calls are mocked in tests (CI environments have no camera/face data) — but the full HTTP/database contract is tested for real: auth, duplicate-code rejection, duplicate-attendance prevention, and report aggregation.

## 📡 API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|--------------|------|
| POST | `/auth/register` | Register admin account | No |
| POST | `/auth/login` | Admin login | No |
| POST | `/employees/register` | Enroll employee with face photos | Yes |
| GET | `/employees` | List all employees | Yes |
| POST | `/attendance/mark` | Submit webcam snapshot, mark attendance | No (kiosk mode) |
| GET | `/attendance/report` | Today's present/absent report | Yes |
| GET | `/attendance/export` | Download CSV report | Yes |

## 🔮 Future Improvements

- Cloud-based recognition (AWS Rekognition) for higher accuracy at scale
- Multi-camera support for multiple entry points
- Liveness detection to prevent photo spoofing
- Mobile app for remote check-in
- Email/Slack notifications for late arrivals

## 📄 License

MIT
