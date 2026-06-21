"""
Pytest suite for Face Recognition Attendance System.
Face recognition itself is mocked here since CI environments don't have
webcams — but the full API contract (auth, CRUD, duplicate prevention,
reporting) is tested against the real database layer.

Run with: pytest test_main.py -v
"""
import os
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

TEST_DB = "test_attendance.db"

import main  # noqa: E402
main.DB_PATH = TEST_DB

from main import app  # noqa: E402

client = TestClient(app)

FAKE_IMAGE_B64 = "ZmFrZWltYWdlZGF0YQ=="  # not a real image; recognition is mocked


@pytest.fixture(autouse=True)
def setup_and_teardown():
    main.init_db()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def get_admin_header():
    client.post("/auth/register", json={"email": "admin@pytest.com", "password": "adminpass1"})
    res = client.post("/auth/login", json={"email": "admin@pytest.com", "password": "adminpass1"})
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_register_and_login():
    res = client.post("/auth/register", json={"email": "a@b.com", "password": "pass1234"})
    assert res.status_code == 201
    res = client.post("/auth/login", json={"email": "a@b.com", "password": "pass1234"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password():
    client.post("/auth/register", json={"email": "c@d.com", "password": "pass1234"})
    res = client.post("/auth/login", json={"email": "c@d.com", "password": "wrong"})
    assert res.status_code == 401


@patch("main.retrain_from_db")
def test_register_employee_requires_auth(mock_retrain):
    res = client.post("/employees/register", json={
        "name": "Test Employee", "employee_code": "E1", "face_images": [FAKE_IMAGE_B64]
    })
    assert res.status_code in (401, 403)


@patch("main.retrain_from_db")
def test_register_employee_success(mock_retrain):
    headers = get_admin_header()
    res = client.post("/employees/register", headers=headers, json={
        "name": "Debotri Ghosh", "employee_code": "EMP001", "face_images": [FAKE_IMAGE_B64]
    })
    assert res.status_code == 201
    assert res.json()["employee_code"] == "EMP001"


@patch("main.retrain_from_db")
def test_register_duplicate_employee_code_fails(mock_retrain):
    headers = get_admin_header()
    client.post("/employees/register", headers=headers, json={
        "name": "Employee A", "employee_code": "DUPE", "face_images": [FAKE_IMAGE_B64]
    })
    res = client.post("/employees/register", headers=headers, json={
        "name": "Employee B", "employee_code": "DUPE", "face_images": [FAKE_IMAGE_B64]
    })
    assert res.status_code == 400


@patch("main.retrain_from_db")
def test_register_employee_no_images_fails(mock_retrain):
    headers = get_admin_header()
    res = client.post("/employees/register", headers=headers, json={
        "name": "No Face", "employee_code": "NOFACE", "face_images": []
    })
    assert res.status_code == 400


@patch("face_service.recognize_face")
@patch("main.retrain_from_db")
def test_mark_attendance_with_match(mock_retrain, mock_recognize):
    headers = get_admin_header()
    reg = client.post("/employees/register", headers=headers, json={
        "name": "Jane Doe", "employee_code": "JD01", "face_images": [FAKE_IMAGE_B64]
    })
    employee_id = reg.json()["id"]

    mock_recognize.return_value = (employee_id, 45.0)
    res = client.post("/attendance/mark", json={"image": FAKE_IMAGE_B64})
    assert res.status_code == 200
    data = res.json()
    assert data["matched"] is True
    assert data["name"] == "Jane Doe"


@patch("face_service.recognize_face")
def test_mark_attendance_no_match(mock_recognize):
    mock_recognize.return_value = (None, None)
    res = client.post("/attendance/mark", json={"image": FAKE_IMAGE_B64})
    assert res.status_code == 200
    assert res.json()["matched"] is False


@patch("face_service.recognize_face")
@patch("main.retrain_from_db")
def test_duplicate_attendance_same_day(mock_retrain, mock_recognize):
    headers = get_admin_header()
    reg = client.post("/employees/register", headers=headers, json={
        "name": "Sam Lee", "employee_code": "SL01", "face_images": [FAKE_IMAGE_B64]
    })
    employee_id = reg.json()["id"]
    mock_recognize.return_value = (employee_id, 40.0)

    first = client.post("/attendance/mark", json={"image": FAKE_IMAGE_B64})
    second = client.post("/attendance/mark", json={"image": FAKE_IMAGE_B64})

    assert first.json()["already_marked"] is False
    assert second.json()["already_marked"] is True


@patch("main.retrain_from_db")
def test_attendance_report_structure(mock_retrain):
    headers = get_admin_header()
    client.post("/employees/register", headers=headers, json={
        "name": "Report Test", "employee_code": "RT01", "face_images": [FAKE_IMAGE_B64]
    })
    res = client.get("/attendance/report", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "present_count" in data
    assert "absent_count" in data
    assert data["total_employees"] == 1
    assert data["absent_count"] == 1  # not marked present yet
