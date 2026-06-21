"""
Face recognition service using OpenCV's LBPH recognizer.
Chosen over face_recognition/dlib because:
  - No C++ compilation step (dlib install often fails on macOS/Windows)
  - opencv-python-headless installs in seconds via pip
  - Good enough accuracy for an attendance-marking demo
"""
import cv2
import numpy as np
import base64
import io
from PIL import Image

FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
RECOGNIZER = cv2.face.LBPHFaceRecognizer_create()

# In-memory label maps (id -> employee_id). Rebuilt from DB on startup.
_label_to_employee = {}
_trained = False


def base64_to_gray_image(b64_string: str) -> np.ndarray:
    """Decode a base64 image string into a grayscale OpenCV image."""
    if "," in b64_string:
        b64_string = b64_string.split(",")[1]
    img_bytes = base64.b64decode(b64_string)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    arr = np.array(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    return gray


def extract_face(gray_img: np.ndarray):
    """Detect the largest face in a grayscale image and return a normalized crop, or None."""
    faces = FACE_CASCADE.detectMultiScale(gray_img, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    # pick the largest detected face
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    face_crop = gray_img[y:y + h, x:x + w]
    face_resized = cv2.resize(face_crop, (200, 200))
    return face_resized


def train_recognizer(employee_faces: dict):
    """
    employee_faces: { employee_id (int): [face_image_b64, ...] }
    Trains the LBPH recognizer on all registered employee faces.
    """
    global _trained, _label_to_employee
    faces = []
    labels = []
    _label_to_employee = {}

    label_counter = 0
    for employee_id, b64_images in employee_faces.items():
        for b64_img in b64_images:
            gray = base64_to_gray_image(b64_img)
            face = extract_face(gray)
            if face is not None:
                faces.append(face)
                labels.append(label_counter)
        _label_to_employee[label_counter] = employee_id
        label_counter += 1

    if not faces:
        _trained = False
        return False

    RECOGNIZER.train(faces, np.array(labels))
    _trained = True
    return True


def recognize_face(b64_image: str, confidence_threshold: float = 80.0):
    """
    Returns (employee_id, confidence) if a confident match is found, else (None, None).
    Lower LBPH confidence score = better match (it's a distance metric).
    """
    if not _trained:
        return None, None

    gray = base64_to_gray_image(b64_image)
    face = extract_face(gray)
    if face is None:
        return None, None

    label, confidence = RECOGNIZER.predict(face)
    if confidence <= confidence_threshold:
        employee_id = _label_to_employee.get(label)
        return employee_id, round(confidence, 2)
    return None, round(confidence, 2)
