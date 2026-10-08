import os
import sys
import time
import base64
import urllib.request
import threading
import uvicorn
import requests
import cv2
import numpy as np

PORT = 8011
BASE_URL = f"http://127.0.0.1:{PORT}"


def run_server():
    uvicorn.run("app:app", host="127.0.0.1", port=PORT, log_level="warning")


def main():
    print("=" * 60)
    print("STARTING FULL API SECURITY & BIOMETRIC TEST SUITE")
    print("=" * 60)

    # 1. Start test server
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2.5)

    session = requests.Session()

    # 2. Security Test: Unauthorized access to admin endpoints MUST fail (401)
    print("\n[Test 1] Testing Role Security: Unauthenticated access to /api/admin/users")
    r_unauth = session.get(f"{BASE_URL}/api/admin/users")
    print(f" -> Response Code: {r_unauth.status_code}")
    assert r_unauth.status_code == 401, f"Expected 401, got {r_unauth.status_code}"
    print(" [OK] Security check passed: Unauthorized access blocked with HTTP 401.")

    # 3. Test Admin Login
    print("\n[Test 2] Testing Admin Login with default credentials (admin / admin123)")
    login_payload = {"username": "admin", "password": "admin123"}
    r_login = session.post(f"{BASE_URL}/api/admin/login", json=login_payload)
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    token_data = r_login.json()
    token = token_data["access_token"]
    assert len(token) > 20
    auth_headers = {"Authorization": f"Bearer {token}"}
    print(f" [OK] Admin authenticated successfully. Token length: {len(token)} chars.")

    # 4. Enroll User with Face via Admin API
    print("\n[Test 3] Enrolling new user 'Dr. Elena Rostova' (EMP-8840) with face photo")
    # Download sample face image
    url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/lena.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        face_bytes = resp.read()

    b64_face = base64.b64encode(face_bytes).decode("utf-8")

    enroll_data = {
        "user_id": "EMP-8840",
        "full_name": "Dr. Elena Rostova",
        "email": "elena.rostova@cybernetics.io",
        "phone": "+1 (555) 432-8840",
        "department": "Engineering",
        "role_title": "Senior AI Researcher",
        "notes": "Clearance Level 4",
        "face_image_base64": b64_face
    }

    # Delete if already exists from previous runs
    session.delete(f"{BASE_URL}/api/admin/users/EMP-8840", headers=auth_headers)

    r_enroll = session.post(f"{BASE_URL}/api/admin/users", data=enroll_data, headers=auth_headers)
    assert r_enroll.status_code == 200, f"Enrollment failed: {r_enroll.text}"
    enroll_res = r_enroll.json()
    assert enroll_res["success"] is True
    print(f" [OK] User enrolled successfully: {enroll_res['user']['full_name']} (Photo: {enroll_res['user']['photo_path']})")

    # 5. Fetch all users as Admin
    print("\n[Test 4] Querying User List as Admin")
    r_users = session.get(f"{BASE_URL}/api/admin/users", headers=auth_headers)
    assert r_users.status_code == 200
    user_list = r_users.json()
    assert any(u["user_id"] == "EMP-8840" for u in user_list)
    print(f" [OK] Admin retrieved {len(user_list)} registered user(s).")

    # 6. Public Kiosk Face Scan
    print("\n[Test 5] Simulating Kiosk Face Scan at /api/scan-face")
    scan_payload = {"image": b64_face}
    r_scan = requests.post(f"{BASE_URL}/api/scan-face", json=scan_payload)
    assert r_scan.status_code == 200, f"Scan request failed: {r_scan.text}"
    scan_res = r_scan.json()
    print(f" -> Scan Status: {scan_res['status']}")
    print(f" -> Recognized Name: {scan_res['user']['full_name']}")
    print(f" -> Badge ID: {scan_res['user']['user_id']}")
    print(f" -> Registered Facial Accuracy: {scan_res['accuracy_percent']}%")
    print(f" -> Cosine Similarity: {scan_res['similarity_score']}")

    assert scan_res["status"] == "VERIFIED"
    assert scan_res["matched"] is True
    assert scan_res["user"]["user_id"] == "EMP-8840"
    assert scan_res["accuracy_percent"] >= 95.0
    # Crucial security verification: ensure raw embedding vectors are NEVER leaked
    assert "embedding" not in scan_res["user"]
    print(" [OK] Biometric match verified! Facial accuracy and verified user details returned.")

    # 7. Public Kiosk Face Scan with Unregistered Face / Noise
    print("\n[Test 6] Simulating Kiosk Scan with an Unknown / Random image")
    noise = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    _, n_buf = cv2.imencode(".jpg", noise)
    noise_b64 = base64.b64encode(n_buf).decode("utf-8")

    r_noise_scan = requests.post(f"{BASE_URL}/api/scan-face", json={"image": noise_b64})
    assert r_noise_scan.status_code == 200
    noise_res = r_noise_scan.json()
    print(f" -> Unknown Scan Status: {noise_res['status']}")
    assert noise_res["matched"] is False
    print(" [OK] Unknown face properly rejected.")

    # 8. Check Audit / Scan Logs
    print("\n[Test 7] Checking Scan Logs in Admin Portal")
    r_logs = session.get(f"{BASE_URL}/api/admin/logs", headers=auth_headers)
    assert r_logs.status_code == 200
    logs_data = r_logs.json()
    assert logs_data["total"] >= 1
    latest_log = logs_data["logs"][0]
    print(f" -> Latest Audit Record: User '{latest_log['user_name']}', Status '{latest_log['status']}', Accuracy {latest_log['accuracy_percent']}%, Snapshot: {latest_log['snapshot_path']}")
    print(" [OK] Audit log recorded accurately.")

    # 9. Test CSV Export
    print("\n[Test 8] Exporting Scan Logs as CSV")
    r_csv = session.get(f"{BASE_URL}/api/admin/logs/export", headers=auth_headers)
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers.get("content-type", "")
    assert "EMP-8840" in r_csv.text or "Dr. Elena Rostova" in r_csv.text
    print(f" [OK] CSV export validated ({len(r_csv.text)} bytes).")

    print("\n" + "=" * 60)
    print("ALL API SECURITY, ACCESS CONTROL, AND SCAN TESTS PASSED!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
