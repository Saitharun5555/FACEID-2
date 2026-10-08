import os
import cv2
import numpy as np
import urllib.request
import base64

from auth import hash_password, verify_password, create_access_token
from config import BASE_DIR, DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
from database import SessionLocal, Base, engine
from models import Admin, User, ScanLog, SystemSetting
from face_engine import face_engine


def test_auth():
    print("\n--- Testing Authentication ---")
    pwd = "secret_password_123"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False
    print(" [OK] Bcrypt password hashing & verification passed.")

    token = create_access_token({"sub": "admin"})
    assert isinstance(token, str) and len(token) > 20
    print(" [OK] JWT Token generation passed.")


def test_face_pipeline():
    print("\n--- Testing Face Pipeline & Accuracy Calculation ---")
    # 1. Download sample face for testing
    url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req)
    nparr = np.asarray(bytearray(resp.read()), dtype=np.uint8)
    sample_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 2. Test registration processing
    _, buffer = cv2.imencode(".jpg", sample_img)
    b64_str = base64.b64encode(buffer).decode("utf-8")

    success, msg, cropped, emb, meta = face_engine.process_face_registration(b64_str)
    assert success is True, f"Registration failed: {msg}"
    assert len(emb) == 128, f"Expected 128-D vector, got {len(emb)}"
    assert cropped.shape == (250, 250, 3)
    print(" [OK] Face detection, cropping, and 128-D embedding extraction passed.")

    # 3. Test accuracy calculation
    acc_perfect = face_engine.calculate_accuracy_percentage(1.0, 0.363)
    acc_threshold = face_engine.calculate_accuracy_percentage(0.363, 0.363)
    acc_low = face_engine.calculate_accuracy_percentage(0.15, 0.363)
    print(f" [OK] Accuracy mapping tests: Score 1.0 -> {acc_perfect}%, Score 0.363 -> {acc_threshold}%, Score 0.15 -> {acc_low}%")
    assert acc_perfect >= 99.0
    assert 69.5 <= acc_threshold <= 70.5
    assert acc_low < 50.0

    # 4. Test identification against database candidate
    registered_candidates = [{
        "user_id": "EMP-001",
        "full_name": "Test User Alpha",
        "embedding": emb
    }]

    # Match identical image
    res_match = face_engine.identify_face(b64_str, registered_candidates)
    assert res_match["status"] == "VERIFIED"
    assert res_match["matched"] is True
    assert res_match["user"]["user_id"] == "EMP-001"
    assert res_match["accuracy_percent"] >= 95.0
    print(f" [OK] Face identification match verified: {res_match['user']['full_name']} with {res_match['accuracy_percent']}% accuracy.")

    # Match against synthetic non-face / random noise image
    noise_img = np.random.randint(0, 255, (250, 250, 3), dtype=np.uint8)
    _, noise_buf = cv2.imencode(".jpg", noise_img)
    noise_b64 = base64.b64encode(noise_buf).decode("utf-8")
    res_noise = face_engine.identify_face(noise_b64, registered_candidates)
    assert res_noise["matched"] is False
    print(f" [OK] Non-matching image correctly rejected: status = {res_noise['status']}.")


if __name__ == "__main__":
    test_auth()
    test_face_pipeline()
    print("\n================ ALL INTERNAL TESTS PASSED ================\n")
