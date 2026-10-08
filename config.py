# ==============================================================================
# FaceID Biometric Recognition & Role-Based Access Control System
# Copyright (c) 2026 Saitharun Cherukuri. All rights reserved.
# Author: Saitharun Cherukuri
# ==============================================================================

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'faceid.db'}")

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "faceid_super_secret_jwt_key_2026_xyz_secure_auth")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Admin credentials default (can be updated from dashboard)
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Biometric Model paths
YUNET_MODEL_PATH = str(BASE_DIR / "models" / "yunet.onnx")
SFACE_MODEL_PATH = str(BASE_DIR / "models" / "sface.onnx")

# Face recognition thresholds
# SFace default cosine threshold is 0.363 (higher = stricter, lower = looser)
DEFAULT_COSINE_THRESHOLD = 0.363
# Minimum face detection confidence
MIN_DETECTION_CONFIDENCE = 0.65

# Upload directories
UPLOAD_DIR_FACES = BASE_DIR / "static" / "uploads" / "faces"
UPLOAD_DIR_SNAPSHOTS = BASE_DIR / "static" / "uploads" / "snapshots"

# Ensure directories exist
UPLOAD_DIR_FACES.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
