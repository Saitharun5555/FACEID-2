# ==============================================================================
# FaceID Biometric Recognition & Role-Based Access Control System
# Copyright (c) 2026 Saitharun Cherukuri. All rights reserved.
# Author: Saitharun Cherukuri
# ==============================================================================

import os
import sys
import webbrowser
import threading
import time
import uvicorn


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")


if __name__ == "__main__":
    port = 8000
    host = "0.0.0.0"

    print("=" * 65)
    print("      FACEID BIOMETRIC RECOGNITION & ACCESS SYSTEM")
    print("      (c) 2026 Saitharun Cherukuri. All rights reserved.")
    print("=" * 65)
    print(" [+] Engine: OpenCV YuNet (Detector) + SFace (Deep Recognizer)")
    print(" [+] Database: SQLite / Encrypted Biometrics")
    print(" [+] Role Security: Strictly Admin-Protected Database Access")
    print(" [+] Author: Saitharun Cherukuri")
    print("-" * 65)
    print(f" [*] Face Scanner Terminal (Kiosk): http://localhost:{port}/")
    print(f" [*] Admin Control Portal:         http://localhost:{port}/admin")
    print(f" [*] Default Admin Login:          admin / admin123")
    print("=" * 65)

    # Launch browser automatically
    threading.Thread(target=open_browser, daemon=True).start()

    # Start Uvicorn Server
    uvicorn.run("app:app", host=host, port=port, log_level="info")
